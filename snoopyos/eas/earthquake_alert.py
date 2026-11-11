#!/usr/bin/env python3
"""SnoopyOS EAS: alertas informativos de terremotos com dados públicos do USGS."""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.request
import urllib.error


FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_hour.geojson"
POLL_SECONDS = 120
DEFAULT_MIN_MAGNITUDE = 4.5
SEEN_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "snoopyos" / "eas-seen.json"

COUNTRY_FLAGS = {
    "argentina": "🇦🇷", "australia": "🇦🇺", "bolivia": "🇧🇴", "brazil": "🇧🇷",
    "brasil": "🇧🇷", "canada": "🇨🇦", "chile": "🇨🇱", "china": "🇨🇳",
    "colombia": "🇨🇴", "costa rica": "🇨🇷", "ecuador": "🇪🇨", "el salvador": "🇸🇻",
    "france": "🇫🇷", "frança": "🇫🇷", "germany": "🇩🇪", "alemanha": "🇩🇪",
    "greece": "🇬🇷", "grécia": "🇬🇷", "indonesia": "🇮🇩", "indonésia": "🇮🇩",
    "iran": "🇮🇷", "italy": "🇮🇹", "itália": "🇮🇹", "japan": "🇯🇵", "japão": "🇯🇵",
    "mexico": "🇲🇽", "méxico": "🇲🇽", "new zealand": "🇳🇿", "nova zelândia": "🇳🇿",
    "peru": "🇵🇪", "philippines": "🇵🇭", "filipinas": "🇵🇭", "portugal": "🇵🇹",
    "russia": "🇷🇺", "rússia": "🇷🇺", "south korea": "🇰🇷", "coreia do sul": "🇰🇷",
    "taiwan": "🇹🇼", "turkey": "🇹🇷", "türkiye": "🇹🇷", "turquia": "🇹🇷",
    "united states": "🇺🇸", "usa": "🇺🇸", "estados unidos": "🇺🇸",
    "uk": "🇬🇧", "united kingdom": "🇬🇧", "reino unido": "🇬🇧",
}

def minimum_magnitude() -> float:
    try:
        value = float(os.environ.get("SNOOPYOS_EAS_MIN_MAGNITUDE", DEFAULT_MIN_MAGNITUDE))
        return min(9.9, max(4.5, value))
    except ValueError:
        return DEFAULT_MIN_MAGNITUDE

def event_country(place: str) -> tuple[str, str]:
    tail = place.rsplit(",", 1)[-1].strip() if "," in place else ""
    key = tail.casefold()
    return (COUNTRY_FLAGS.get(key, "🌐"), tail or "Região não identificada")

def load_events(payload: dict, minimum: float = DEFAULT_MIN_MAGNITUDE) -> list[dict]:
    events = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        try:
            magnitude = float(props.get("mag"))
        except (TypeError, ValueError):
            continue
        if magnitude < minimum or not props.get("id"):
            continue
        place = str(props.get("place") or "Localização não informada")
        flag, country = event_country(place)
        events.append({
            "id": str(props["id"]),
            "magnitude": magnitude,
            "place": place,
            "country": country,
            "flag": flag,
            "time": int(props.get("time") or 0),
            "url": str(props.get("url") or "https://earthquake.usgs.gov/"),
        })
    return sorted(events, key=lambda item: item["time"], reverse=True)

def fetch_events() -> list[dict]:
    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "SnoopyOS-EAS/1.0 (informational earthquake monitor)"}
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return load_events(payload, minimum_magnitude())

def read_seen() -> set[str]:
    try:
        values = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return {str(value) for value in values[-150:]}
    except (OSError, ValueError, TypeError):
        return set()

def remember(event_id: str) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    values = list(read_seen())
    values.append(event_id)
    SEEN_FILE.write_text(json.dumps(values[-150:]), encoding="utf-8")

def show_alert(event: dict) -> None:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    dialog = Gtk.MessageDialog(
        parent=None,
        flags=Gtk.DialogFlags.MODAL,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.CLOSE,
        text="ISSO NÃO É UM TESTE"
    )
    dialog.set_title("SnoopyOS | Alerta de terremoto")
    dialog.set_default_size(620, 360)
    dialog.set_keep_above(True)
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.format_secondary_text(
        "Um terremoto foi detectado.\n"
        f"País/região: {event['flag']} {event['country']}\n"
        f"Local: {event['place']}\n"
        f"\nMagnitude: {event['magnitude']:.1f}\n\n"
        "Fique em calma e vá para um lugar seguro. "
        "Siga as orientações das autoridades locais.\n\n"
        "Para segurança de todos, este alerta será encerrado automaticamente "
        "após 60 segundos. O computador não será desligado."
    )
    dialog.set_resizable(True)
    dialog.show_all()
    GLib.timeout_add_seconds(60, lambda: (dialog.response(Gtk.ResponseType.CLOSE), False)[1])
    dialog.run()
    dialog.destroy()

class Monitor:
    def __init__(self):
        self.seen = read_seen()
        self.check()

    def check(self):
        try:
            events = fetch_events()
            fresh = [event for event in events if event["id"] not in self.seen]
            for event in fresh[:3]:
                self.seen.add(event["id"])
                remember(event["id"])
                show_alert(event)
        except (OSError, ValueError, urllib.error.URLError, TimeoutError) as error:
            print(f"SnoopyOS EAS: consulta indisponível: {error}", flush=True)
        return True

def main():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib, Gdk
    Gdk.set_program_class("SnoopyOS-EAS")
    monitor = Monitor()
    GLib.timeout_add_seconds(POLL_SECONDS, monitor.check)
    Gtk.main()

if __name__ == "__main__":
    main()
