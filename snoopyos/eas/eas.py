#!/usr/bin/env python3
"""Central EAS do SnoopyOS para Xfce."""
from array import array
from dataclasses import asdict
import json
from math import sin, tau
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile
from threading import Thread
import wave

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from eas_data import ALERT_SOURCES, DEFAULT_CITIES, DEFAULT_COUNTRIES, City
from eas_data import active_alerts, forecast, search_cities


CONFIG = Path(GLib.get_user_config_dir()) / "snoopyos/eas.json"
SOUND_PROFILE = "América (Estados Unidos)"


def saved_city():
    try:
        return City(**json.loads(CONFIG.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError):
        return DEFAULT_CITIES["BR"]


def write_test_sound(path):
    # Três pulsos melódicos inspirados no ritmo do vídeo, sem os tons codificados do EAS.
    rate = 24000
    samples = array("h")
    for frequency, duration in ((520, 0.28), (650, 0.28), (590, 0.44)):
        frames = round(rate * duration)
        for index in range(frames):
            fade = min(1, index / 480, (frames - index - 1) / 960)
            samples.append(round(5800 * fade * sin(tau * frequency * index / rate)))
        samples.extend([0] * round(rate * 0.16))
    if sys.byteorder == "big":
        samples.byteswap()
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())


def play_test_sound():
    with NamedTemporaryFile(suffix=".wav") as sound:
        write_test_sound(sound.name)
        for player in ("pw-play", "paplay", "aplay"):
            executable = shutil.which(player)
            if not executable:
                continue
            try:
                subprocess.run([executable, sound.name], check=True, timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False


def label(text="", *, muted=False):
    widget = Gtk.Label(label=text, xalign=0, wrap=True)
    if muted:
        widget.get_style_context().add_class("dim-label")
    return widget


def heading(text):
    widget = label()
    widget.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
    return widget


class Central(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="SnoopyOS · Central EAS")
        self.set_default_size(590, 570)
        self.city = saved_city()
        self.matches = []
        self.known_alerts = set()
        self.pending = 0
        self.closed = False

        header = Gtk.HeaderBar(title="Central EAS", subtitle="SnoopyOS", show_close_button=True)
        self.set_titlebar(header)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=16)
        self.add(layout)
        layout.pack_start(heading("Sistema de Alarme de Emergência"), False, False, 0)
        self.location = label()
        layout.pack_start(self.location, False, False, 0)

        controls = Gtk.Box(spacing=6)
        layout.pack_start(controls, False, False, 0)
        self.country = Gtk.ComboBoxText()
        for code, name in DEFAULT_COUNTRIES.items():
            self.country.append(code, name)
        self.country.set_active_id(self.city.country)
        self.country.set_tooltip_text("País dos avisos e da previsão")
        self.country.connect("changed", self.change_country)
        controls.pack_start(self.country, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Nome da cidade", max_length=120)
        self.search.connect("activate", self.find_city)
        controls.pack_start(self.search, True, True, 0)
        self.find = Gtk.Button(label="Buscar")
        self.find.connect("clicked", self.find_city)
        controls.pack_start(self.find, False, False, 0)
        self.reload = Gtk.Button(label="Atualizar")
        self.reload.connect("clicked", self.refresh)
        controls.pack_start(self.reload, False, False, 0)
        self.choices = Gtk.ComboBoxText(no_show_all=True)
        self.choices.connect("changed", self.choose_city)
        layout.pack_start(self.choices, False, False, 0)
        self.search_status = label(muted=True)
        layout.pack_start(self.search_status, False, False, 0)

        tabs = Gtk.Notebook()
        layout.pack_start(tabs, True, True, 0)
        alerts = self.add_tab(tabs, "Alertas")
        alerts.pack_start(heading("Avisos meteorológicos oficiais"), False, False, 0)
        self.alert_status = label()
        alerts.pack_start(self.alert_status, False, False, 0)
        self.alert_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        alerts.pack_start(self.alert_list, False, False, 0)
        self.source = Gtk.LinkButton(halign=Gtk.Align.START)
        alerts.pack_start(self.source, False, False, 0)
        alerts.pack_start(Gtk.Separator(), False, False, 2)
        alerts.pack_start(heading("Teste de som · simulação local"), False, False, 0)
        alerts.pack_start(label(f"Perfil para Brasil e EUA · {SOUND_PROFILE}"), False, False, 0)
        self.test = Gtk.Button(label="Testar som", halign=Gtk.Align.START)
        self.test.connect("clicked", self.test_sound)
        alerts.pack_start(self.test, False, False, 0)
        self.sound_status = label("Teste o som a qualquer momento", muted=True)
        alerts.pack_start(self.sound_status, False, False, 0)
        self.sound_on_alert = Gtk.CheckButton(label="Tocar som ao receber um novo aviso")
        alerts.pack_start(self.sound_on_alert, False, False, 0)
        alerts.pack_start(label("A central atualiza os avisos enquanto estiver aberta", muted=True),
                          False, False, 0)

        weather = self.add_tab(tabs, "Clima")
        weather.pack_start(heading("Agora"), False, False, 0)
        self.current = label()
        self.conditions = label()
        self.timestamp = label(muted=True)
        for row in (self.current, self.conditions, self.timestamp):
            weather.pack_start(row, False, False, 0)
        weather.pack_start(Gtk.Separator(), False, False, 2)
        weather.pack_start(heading("Previsão de três dias"), False, False, 0)
        self.days = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        weather.pack_start(self.days, False, False, 0)
        credit = Gtk.LinkButton.new_with_label("https://open-meteo.com/", "Open-Meteo · CC BY 4.0")
        credit.set_halign(Gtk.Align.START)
        weather.pack_start(credit, False, False, 0)

        self.timer = GLib.timeout_add_seconds(900, self.refresh)
        self.connect("destroy", self.on_destroy)
        self.show_all()
        self.refresh()

    def add_tab(self, tabs, name):
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9, border_width=14)
        scroll.add(content)
        tabs.append_page(scroll, Gtk.Label(label=name))
        return content

    def on_destroy(self, _window):
        self.closed = True
        GLib.source_remove(self.timer)

    def request(self, operation, render):
        controls = (self.country, self.search, self.find, self.reload, self.choices)
        self.pending += 1
        for control in controls:
            control.set_sensitive(False)

        def done(result):
            if self.closed:
                return
            self.pending -= 1
            if not self.pending:
                for control in controls:
                    control.set_sensitive(True)
            render(result)

        def fetch():
            try:
                result = operation()
            except (OSError, TypeError, ValueError, KeyError, IndexError, AttributeError):
                result = None
            GLib.idle_add(done, result)

        Thread(target=fetch, daemon=True).start()

    def change_country(self, combo):
        code = combo.get_active_id()
        if code:
            self.set_city(DEFAULT_CITIES[code])

    def find_city(self, _widget):
        name = self.search.get_text().strip()
        self.choices.hide()
        if len(name) < 2:
            self.search_status.set_text("Digite pelo menos duas letras para buscar uma cidade")
            return
        self.search_status.set_text("Buscando cidades…")
        country = self.city.country
        self.request(lambda: search_cities(name, country), self.show_matches)

    def show_matches(self, matches):
        if matches is None:
            self.search_status.set_text("A busca está indisponível agora")
        elif not matches:
            self.search_status.set_text("Nenhuma cidade encontrada nesse país")
        elif len(matches) == 1:
            self.set_city(matches[0])
        else:
            self.matches = matches
            self.choices.remove_all()
            self.choices.append_text("Selecione uma cidade")
            for city in matches:
                self.choices.append_text(city.label)
            self.choices.set_active(0)
            self.choices.show()
            self.search_status.set_text("")

    def choose_city(self, combo):
        index = combo.get_active()
        if index > 0:
            self.set_city(self.matches[index - 1])

    def set_city(self, city):
        if city != self.city:
            if self.known_alerts:
                self.get_application().withdraw_notification("weather-warning")
            self.known_alerts.clear()
        self.city = city
        self.choices.hide()
        self.search.set_text("")
        self.search_status.set_text("")
        try:
            CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            GLib.file_set_contents(str(CONFIG), json.dumps(asdict(city)).encode("utf-8"))
        except (OSError, GLib.Error):
            self.search_status.set_text("A cidade será usada até fechar a central")
        self.refresh()

    def refresh(self, _widget=None):
        if self.pending:
            return GLib.SOURCE_CONTINUE
        city = self.city
        provider, url = ALERT_SOURCES[city.country]
        self.location.set_text(city.label)
        self.source.set_uri(url)
        self.source.set_label(f"Abrir fonte oficial · {provider}")
        self.alert_status.set_text(f"Consultando {provider}…")
        self.current.set_text("Consultando o tempo…")
        self.conditions.set_text("")
        self.timestamp.set_text("")
        self.replace_rows(self.alert_list, ())
        self.replace_rows(self.days, ())
        self.request(lambda: forecast(city), self.show_forecast)
        self.request(lambda: active_alerts(city), self.show_alerts)
        return GLib.SOURCE_CONTINUE

    def replace_rows(self, box, rows):
        for child in box.get_children():
            box.remove(child)
        for text in rows:
            box.pack_start(label(text), False, False, 0)
        box.show_all()

    def show_alerts(self, alerts):
        provider = ALERT_SOURCES[self.city.country][0]
        if alerts is None:
            status = f"Consulta ao {provider} indisponível agora"
        elif alerts:
            status = f"Em vigor no ponto de referência da cidade · {provider}"
        else:
            status = f"Nenhum aviso retornado por {provider} para este ponto"
        self.alert_status.set_text(status)
        self.replace_rows(self.alert_list, alerts or ())
        if alerts is None:
            return
        had_alerts = bool(self.known_alerts)
        new_alerts = [alert for alert in alerts if alert not in self.known_alerts]
        self.known_alerts = set(alerts)
        if new_alerts:
            notification = Gio.Notification.new(f"Aviso meteorológico · {provider}")
            notification.set_icon(Gio.ThemedIcon.new("dialog-warning"))
            notification.set_body(f"{self.city.label}\n{new_alerts[0]}")
            self.get_application().send_notification("weather-warning", notification)
            if self.sound_on_alert.get_active():
                self.play_sound("Novo aviso · Tocando o perfil dos EUA…")
        elif not alerts and had_alerts:
            self.get_application().withdraw_notification("weather-warning")

    def show_forecast(self, weather):
        if weather is None:
            self.current.set_text("Previsão indisponível agora · confira a conexão e tente atualizar")
            return
        current, conditions, timestamp, days = weather
        self.current.set_text(current)
        self.conditions.set_text(conditions)
        self.timestamp.set_text(timestamp)
        self.replace_rows(self.days, days)

    def test_sound(self, _button):
        self.play_sound("SIMULAÇÃO LOCAL · Tocando o perfil dos EUA…")

    def play_sound(self, message):
        if not self.test.get_sensitive():
            return
        self.test.set_sensitive(False)
        self.sound_status.set_text(message)

        def finished(played):
            if self.closed:
                return
            self.test.set_sensitive(True)
            status = "Som concluído" if played else "Áudio indisponível · confira a saída de som"
            self.sound_status.set_text(status)

        def play():
            try:
                played = play_test_sound()
            except OSError:
                played = False
            GLib.idle_add(finished, played)

        Thread(target=play, daemon=True).start()


def main():
    app = Gtk.Application(application_id="org.snoopyos.EAS")

    def activate(application):
        window = application.get_active_window() or Central(application)
        window.present()

    app.connect("activate", activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
