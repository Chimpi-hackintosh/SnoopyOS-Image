#!/usr/bin/env python3
"""SnoopyOS Games: painel leve e modo de jogo reversível, sem privilégios de root."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time


def human_size(value: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{value} B"
        value /= 1024
    return "0 B"


def safe_cleanup(days: int = 7, *, roots=None, now=None) -> tuple[int, int]:
    """Remove SOMENTE miniaturas antigas e temporários próprios do SnoopyOS."""
    if not 1 <= days <= 365:
        raise ValueError("days deve ficar entre 1 e 365")
    home_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    allowed_roots = (home_cache / "thumbnails", home_cache / "snoopyos-games" / "tmp")
    paths = allowed_roots if roots is None else tuple(Path(p) for p in roots)
    cutoff = (time.time() if now is None else now) - days * 86400
    count = saved = 0
    for root in paths:
        if root.is_symlink() or not root.is_dir():
            continue
        for directory, subdirs, files in os.walk(root, followlinks=False):
            subdirs[:] = [d for d in subdirs if not (Path(directory) / d).is_symlink()]
            for filename in files:
                path = Path(directory) / filename
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_mtime > cutoff:
                        continue
                    path.unlink()
                    count += 1
                    saved += info.st_size
                except OSError:
                    continue
    return count, saved


def read_mem() -> tuple[int, int]:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, _, value = line.partition(":")
            if name in ("MemTotal", "MemAvailable"):
                values[name] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return values.get("MemTotal", 0), values.get("MemAvailable", 0)


def read_cpu() -> tuple[int, int]:
    try:
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        times = [int(number) for number in fields]
        # guest and guest_nice are already included in user and nice by Linux.
        # Sum user through steal only, avoiding duplicate guest CPU time.
        return sum(times[:8]), times[3] + (times[4] if len(times) > 4 else 0)
    except (OSError, ValueError, IndexError):
        return 0, 0


class GameBoost:
    """Desativa temporariamente o compositor do Xfce, restaurando ao sair."""
    property_name = "/general/use_compositing"

    def __init__(self):
        self.previous = None
        self.changed = False

    def _query(self, *arguments):
        if not shutil.which("xfconf-query"):
            return None
        try:
            result = subprocess.run(
                ["xfconf-query", "-c", "xfwm4", "-p", self.property_name, *arguments],
                capture_output=True, text=True, timeout=3, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def start(self) -> bool:
        if self.previous is not None:
            return True
        current = self._query()
        if current not in ("true", "false"):
            return False
        self.previous = current
        if current == "true":
            self.changed = self._query("-s", "false") is not None
            if not self.changed:
                self.previous = None
                return False
        return True

    def stop(self) -> None:
        if self.changed and self.previous is not None:
            self._query("-s", self.previous)
        self.changed = False
        self.previous = None


def launch_game(command: list[str], *, cleanup: bool = True) -> int:
    if not command:
        raise ValueError("Informe o executável do jogo")
    if cleanup:
        count, saved = safe_cleanup()
        print(f"Limpeza segura: {count} miniaturas/temporários, {human_size(saved)} liberados", flush=True)
    boost = GameBoost()
    activated = boost.start()
    launcher = ["gamemoderun"] if shutil.which("gamemoderun") else []
    env = os.environ.copy()
    env["SNOOPYOS_GAMES"] = "1"
    print("Modo Games:", "Xfce otimizado" if activated else "configuração original", flush=True)
    try:
        return subprocess.call(launcher + command, env=env)
    finally:
        boost.stop()


def show_widget() -> None:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    css = """
    .games-window { background: #101528; border: 2px solid #34416b; border-radius: 22px; }
    .games-title { color: #f7f7ff; font-weight: 900; font-size: 23px; }
    .games-caption { color: #9caad1; font-size: 12px; }
    .games-stat { color: #d8e9ff; font-weight: 700; font-size: 15px; }
    .games-card { background: #202943; border-radius: 14px; padding: 11px; }
    .games-button { background: #405dff; color: white; font-weight: bold;
                    border-radius: 12px; border: none; padding: 10px; }
    .games-button:hover { background: #5b75ff; }
    .games-turbo { background: #00ae99; }
    .games-turbo:hover { background: #00c7b1; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    window = Gtk.Window(title="SnoopyOS Games")
    window.set_default_size(355, 360)
    window.set_resizable(False)
    window.set_skip_taskbar_hint(True)
    window.set_keep_below(True)
    window.get_style_context().add_class("games-window")
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    outer.set_border_width(18)
    window.add(outer)

    def label(text, style):
        result = Gtk.Label(label=text)
        result.set_xalign(0)
        result.get_style_context().add_class(style)
        return result

    outer.pack_start(label("🐾 SnoopyOS Games", "games-title"), False, False, 0)
    outer.pack_start(label("Seu cantinho gamer, leve e rápido ⚡", "games-caption"), False, False, 0)

    stats = Gtk.Grid(column_spacing=10, row_spacing=10)
    outer.pack_start(stats, False, False, 0)
    items = {}
    for index, (key, title) in enumerate(
            (("cpu", "⚡ CPU"), ("ram", "🧠 RAM"),
             ("disk", "💾 Espaço livre"), ("mode", "🎮 Modo FPS"))):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        card.get_style_context().add_class("games-card")
        card.pack_start(label(title, "games-caption"), False, False, 0)
        value = label("Calculando...", "games-stat")
        value.set_size_request(140, -1)
        card.pack_start(value, False, False, 0)
        stats.attach(card, index % 2, index // 2, 1, 1)
        items[key] = value

    boost = GameBoost()
    message = label("Sem exclusão de saves ou arquivos pessoais", "games-caption")
    message.set_line_wrap(True)

    button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    outer.pack_start(button_box, False, False, 0)

    turbo = Gtk.Button(label="🚀 Ativar modo FPS")
    turbo.get_style_context().add_class("games-button")
    turbo.get_style_context().add_class("games-turbo")
    button_box.pack_start(turbo, False, False, 0)

    choose = Gtk.Button(label="🎮 Escolher jogo para iniciar")
    choose.get_style_context().add_class("games-button")
    button_box.pack_start(choose, False, False, 0)

    clean = Gtk.Button(label="✨ Limpar miniaturas antigas")
    clean.get_style_context().add_class("games-button")
    button_box.pack_start(clean, False, False, 0)
    outer.pack_start(message, False, False, 0)
    outer.pack_start(label("FPS depende da GPU, do jogo e das configurações", "games-caption"),
                     False, False, 0)

    def toggle(_button):
        if boost.previous is not None:
            boost.stop()
            turbo.set_label("🚀 Ativar modo FPS")
            message.set_text("Modo normal restaurado")
        elif boost.start():
            turbo.set_label("🟢 Desativar modo FPS")
            message.set_text("Compositor do Xfce pausado temporariamente")
        else:
            message.set_text("Modo FPS precisa do Xfce com xfconf-query")

    def run_clean(_button):
        count, saved = safe_cleanup()
        message.set_text(f"{count} arquivos temporários, {human_size(saved)} liberados")

    def choose_game(_button):
        dialog = Gtk.FileChooserDialog(
            title="Escolha o executável Linux do jogo", parent=window,
            action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                filename = dialog.get_filename()
                if not filename or not os.access(filename, os.X_OK):
                    message.set_text("Escolha um arquivo executável do Linux")
                else:
                    subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                      "play", filename], start_new_session=True)
                    message.set_text("Jogo iniciado com limpeza segura e modo FPS")
        except OSError as error:
            message.set_text(f"Não foi possível iniciar: {error}")
        finally:
            dialog.destroy()

    turbo.connect("clicked", toggle)
    choose.connect("clicked", choose_game)
    clean.connect("clicked", run_clean)
    previous_cpu = [read_cpu()]

    def update():
        total, idle = read_cpu()
        old_total, old_idle = previous_cpu[0]
        elapsed = total - old_total
        usage = 100 * (1 - (idle - old_idle) / elapsed) if elapsed > 0 else 0
        items["cpu"].set_text(f"{max(0, min(100, usage)):.0f}%")
        previous_cpu[0] = (total, idle)
        mem_total, mem_free = read_mem()
        items["ram"].set_text(f"{100 * (mem_total - mem_free) / mem_total:.0f}% usada"
                              if mem_total else "Indisponível")
        items["disk"].set_text(human_size(shutil.disk_usage(Path.home()).free))
        items["mode"].set_text("Ativo ⚡" if boost.previous is not None else "Normal")
        return True

    def close(*_):
        boost.stop()
        Gtk.main_quit()

    window.connect("destroy", close)
    GLib.timeout_add_seconds(2, update)
    update()
    window.show_all()
    window.move(max(0, Gdk.Screen.get_default().get_width() - 380), 65)
    try:
        build = json.loads((Path(__file__).resolve().parent / "support-version.json").read_text(encoding="utf-8"))
        if build.get("app") == "SnoopyOS-Games" and build.get("version"):
            from support_notice import attach_gtk
            attach_gtk(window, "SnoopyOS-Games", build["version"])
    except (OSError, ValueError, TypeError, AttributeError):
        pass  # A source checkout without a release tag has no known installed version.
    Gtk.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("widget", help="Abre os widgets gráficos")
    commands.add_parser("status", help="Consulta memória e espaço livre")
    clean = commands.add_parser("cleanup", help="Limpeza restrita a miniaturas/temporários antigos")
    clean.add_argument("--days", type=int, default=7, help="Idade mínima, em dias (1-365)")
    play = commands.add_parser("play", help="Roda um jogo e restaura os ajustes ao fechar")
    play.add_argument("game", nargs=argparse.REMAINDER, help="Comando do jogo e argumentos")
    args = parser.parse_args()
    if args.action == "widget":
        show_widget()
    elif args.action == "status":
        total, free = read_mem()
        print(f"RAM: {human_size(total - free)} / {human_size(total)}")
        print(f"Disco livre: {human_size(shutil.disk_usage(Path.home()).free)}")
        print(f"GameMode instalado: {'sim' if shutil.which('gamemoderun') else 'não (opcional)'}")
    elif args.action == "cleanup":
        count, saved = safe_cleanup(args.days)
        print(f"{count} arquivos temporários apagados, {human_size(saved)} liberados")
    elif args.action == "play":
        game = args.game[1:] if args.game and args.game[0] == "--" else args.game
        if not game:
            parser.error("Use: play -- executavel-do-jogo [argumentos]")
        return launch_game(game)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"SnoopyOS Games: {error}", file=sys.stderr)
        sys.exit(1)

