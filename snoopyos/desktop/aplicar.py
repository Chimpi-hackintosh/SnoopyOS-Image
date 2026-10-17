#!/usr/bin/python3
"""Aplica o desktop SnoopyOS na sessão Xfce atual, com backup reversível."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

VERSION = "0.1"
CHANNELS = ("xfce4-panel", "xfce4-desktop", "xsettings", "xfce4-keyboard-shortcuts")


def xdg(name, fallback):
    value = os.environ.get(name)
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


CONFIG = xdg("XDG_CONFIG_HOME", ".config")
DATA = xdg("XDG_DATA_HOME", ".local/share")
STATE = xdg("XDG_STATE_HOME", ".local/state") / "snoopyos"
MARKER = STATE / "layout.json"
ASSETS = DATA / "snoopyos" / "assets"


def run(argv):
    return subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          check=False)


class Xfconf:
    def __init__(self):
        import gi
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gio, GLib, Gdk
        self.GLib, self.Gdk = GLib, Gdk
        if not Gdk.init_check([])[0]:
            raise RuntimeError("Não foi possível acessar a tela da sessão X11")
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.call("ListChannels", None)

    def call(self, method, value):
        from gi.repository import Gio
        return self.connection.call_sync(
            "org.xfce.Xfconf", "/org/xfce/Xfconf", "org.xfce.Xfconf", method,
            value, None, Gio.DBusCallFlags.NONE, 10000, None)

    def props(self, channel):
        if channel not in self.call("ListChannels", None).unpack()[0]:
            return self.GLib.Variant("a{sv}", {})
        return self.call("GetAllProperties", self.GLib.Variant(
            "(ss)", (channel, "/"))).get_child_value(0)

    def active(self, service):
        from gi.repository import Gio
        return self.connection.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", "NameHasOwner",
            self.GLib.Variant("(s)", (service,)), None,
            Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]

    def reset(self, channel):
        if channel in self.call("ListChannels", None).unpack()[0]:
            self.call("ResetProperty", self.GLib.Variant("(ssb)", (channel, "/", True)))

    def variant(self, channel, key, value):
        self.call("SetProperty", self.GLib.Variant("(ssv)", (channel, key, value)))

    def set(self, channel, key, signature, value):
        self.variant(channel, key, self.GLib.Variant(signature, value))

    def array(self, channel, key, signature, values):
        self.set(channel, key, "av", [self.GLib.Variant(signature, v) for v in values])


def desktop_path(override):
    if override:
        return Path(override).expanduser().resolve()
    if shutil.which("xdg-user-dir"):
        result = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True,
                                text=True, check=True)
        path = Path(result.stdout.strip())
        if path.is_absolute() and path != Path.home():
            return path
    return Path.home() / "Desktop"


def affected_files(desktop):
    files = [CONFIG / "gtk-3.0/gtk.css", CONFIG / "gtk-3.0/snoopyos.css",
            CONFIG / "xfce4/panel/launcher-102/snoopyos-terminal.desktop",
            desktop / "SnoopyOS-Terminal.desktop", MARKER]
    files.extend(path for path in (CONFIG / "xfce4/desktop").glob("icons*") if path.is_file())
    return files


def backup(xf, desktop):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = STATE / "backups" / (stamp + "-" + uuid.uuid4().hex[:6])
    directory.mkdir(parents=True, exist_ok=False)
    entries = []
    for index, path in enumerate(affected_files(desktop)):
        if path.is_symlink():
            raise RuntimeError(f"O arquivo é um link simbólico: {path}")
        entry = {"path": str(path), "existed": path.is_file(), "index": index}
        if entry["existed"]:
            shutil.copy2(path, directory / str(index))
        entries.append(entry)
    channels = {channel: xf.props(channel).print_(True) for channel in CHANNELS}
    (directory / "snapshot.json").write_text(json.dumps(
        {"files": entries, "channels": channels}, ensure_ascii=False, indent=2))
    return directory


def restore_snapshot(xf, directory):
    snapshot = json.loads((directory / "snapshot.json").read_text())
    if xf.active("org.xfce.Panel"):
        run(["xfce4-panel", "--quit"])
    run(["xfdesktop", "--quit"])
    time.sleep(0.3)
    for channel, source in snapshot["channels"].items():
        xf.reset(channel)
        values = xf.GLib.Variant.parse(None, source, None, None)
        for index in range(values.n_children()):
            entry = values.get_child_value(index)
            key = entry.get_child_value(0).get_string()
            value = entry.get_child_value(1).get_variant()
            xf.variant(channel, key, value)
    for entry in snapshot["files"]:
        path = Path(entry["path"])
        if entry["existed"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / str(entry["index"]), path)
        else:
            path.unlink(missing_ok=True)
    refresh()


def refresh():
    run(["xfdesktop", "--quit"])
    time.sleep(0.5)
    environment = os.environ.copy()
    environment.setdefault("XDG_CURRENT_DESKTOP", "XFCE")
    environment.setdefault("XDG_MENU_PREFIX", "xfce-")
    environment.pop("DESKTOP_AUTOSTART_ID", None)
    for program in ("xfdesktop", "xfce4-panel"):
        subprocess.Popen([program], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         env=environment)


def wallpaper(xf):
    channel = "xfce4-desktop"
    paths = set()
    for key in xf.props(channel).unpack():
        if key.startswith("/backdrop/") and "/workspace" in key:
            paths.add(key.rsplit("/", 1)[0])
    display = xf.Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("Não foi possível acessar a tela da sessão X11")
    screen = display.get_default_screen()
    for index in range(display.get_n_monitors()):
        connector = screen.get_monitor_plug_name(index)
        for name in (str(index), connector):
            if name:
                paths.add(f"/backdrop/screen0/monitor{name}/workspace0")
    paths.add("/backdrop/screen0/monitor0/workspace0")
    for path in paths:
        xf.set(channel, path + "/last-image", "s", str(ASSETS / "papel-de-parede.svg"))
        xf.set(channel, path + "/image-style", "i", 5)
        xf.set(channel, path + "/color-style", "i", 0)
        xf.set(channel, path + "/backdrop-cycle-enable", "b", False)
    xf.set(channel, "/backdrop/single-workspace-mode", "b", True)
    xf.set(channel, "/backdrop/single-workspace-number", "i", 0)


def configure(xf, desktop):
    source = Path(__file__).resolve().parent / "assets"
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, ASSETS, dirs_exist_ok=True)
    css = CONFIG / "gtk-3.0/gtk.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS / "snoopyos.css", css.parent / "snoopyos.css")
    current = css.read_text() if css.exists() else ""
    line = '@import url("snoopyos.css");\n'
    if line not in current:
        css.write_text(line + current)

    launcher = "\n".join([
        "[Desktop Entry]", "Version=1.0", "Type=Application", "Name=Terminal",
        "Comment=Abrir o terminal do Linux", "Exec=xfce4-terminal",
        "TryExec=xfce4-terminal", f"Icon={ASSETS / 'terminal.svg'}",
        "Terminal=false", "Categories=System;TerminalEmulator;", "StartupNotify=true", ""])
    panel_launcher = CONFIG / "xfce4/panel/launcher-102/snoopyos-terminal.desktop"
    panel_launcher.parent.mkdir(parents=True, exist_ok=True)
    panel_launcher.write_text(launcher)
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / "SnoopyOS-Terminal.desktop"
    shortcut.write_text(launcher)
    shortcut.chmod(0o755)
    if shutil.which("gio"):
        run(["gio", "set", str(shortcut), "metadata::trusted", "true"])

    if xf.active("org.xfce.Panel"):
        run(["xfce4-panel", "--quit"])
    channel = "xfce4-panel"
    xf.reset(channel)
    xf.set(channel, "/configver", "i", 2)
    xf.array(channel, "/panels", "i", [1])
    panel = "/panels/panel-1"
    height = xf.Gdk.Display.get_default().get_monitor(0).get_geometry().height
    size = min(108, max(64, round(height * 0.11)))
    values = {"position": ("s", "p=10;x=0;y=0"), "position-locked": ("b", True),
              "length": ("u", 100), "length-adjust": ("b", False),
              "size": ("u", size), "nrows": ("u", 1),
              "icon-size": ("u", size - 18), "mode": ("u", 0),
              "autohide-behavior": ("u", 0), "background-style": ("u", 1),
              "enter-opacity": ("u", 100), "leave-opacity": ("u", 100)}
    for key, (signature, value) in values.items():
        xf.set(channel, panel + "/" + key, signature, value)
    xf.array(channel, panel + "/background-rgba", "d", [254/255, 241/255, 188/255, 1.0])
    xf.array(channel, panel + "/plugin-ids", "i", [101, 102, 103, 104])
    plugins = {101: "applicationsmenu", 102: "launcher", 103: "tasklist", 104: "separator"}
    for index, plugin in plugins.items():
        xf.set(channel, f"/plugins/plugin-{index}", "s", plugin)
    menu = "/plugins/plugin-101/"
    xf.set(channel, menu + "button-icon", "s", str(ASSETS / "snoopy-menu.svg"))
    xf.set(channel, menu + "button-title", "s", "+")
    xf.set(channel, menu + "show-button-title", "b", True)
    xf.set(channel, menu + "show-menu-icons", "b", True)
    xf.array(channel, "/plugins/plugin-102/items", "s", ["snoopyos-terminal.desktop"])
    xf.set(channel, "/plugins/plugin-103/show-labels", "b", False)
    xf.set(channel, "/plugins/plugin-103/flat-buttons", "b", True)
    xf.set(channel, "/plugins/plugin-104/expand", "b", True)
    xf.set(channel, "/plugins/plugin-104/style", "u", 0)
    desktop_channel = "xfce4-desktop"
    for key, signature, value in [("style", "i", 2), ("icon-size", "u", 112),
                                  ("use-custom-font-size", "b", True),
                                  ("confirm-sorting", "b", False),
                                  ("font-size", "d", 22.0)]:
        xf.set(desktop_channel, "/desktop-icons/" + key, signature, value)
    for item in ("show-home", "show-filesystem", "show-trash", "show-removable"):
        xf.set(desktop_channel, "/desktop-icons/file-icons/" + item, "b", False)
    wallpaper(xf)
    xf.set("xsettings", "/Net/ThemeName", "s", "Adwaita")
    xf.set("xsettings", "/Net/IconThemeName", "s", "Adwaita")
    xf.set("xfce4-keyboard-shortcuts", "/commands/custom/<Primary><Alt>t",
           "s", "xfce4-terminal")
    xf.set("xfce4-keyboard-shortcuts", "/commands/custom/Super_L",
           "s", "xfce4-popup-applicationsmenu")
    run(["xfdesktop", "--arrange"])
    refresh()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true", help="Restaurar o backup anterior")
    parser.add_argument("--autostart", action="store_true", help="Aplicar apenas no primeiro login")
    parser.add_argument("--desktop-dir", help="Pasta de área de trabalho alternativa")
    args = parser.parse_args()
    if os.environ.get("SUDO_USER"):
        raise RuntimeError("Execute sem sudo, como usuário da sessão Xfce")
    if not os.environ.get("DISPLAY") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise RuntimeError("Abra o Terminal dentro de uma sessão Xfce/X11 e execute novamente")
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        raise RuntimeError("Esta versão usa a sessão Xfce/X11")
    if args.autostart and MARKER.exists():
        return
    if args.autostart:
        time.sleep(3)
    for name in ("xfce4-panel", "xfdesktop", "xfce4-terminal"):
        if not shutil.which(name):
            raise RuntimeError(f"Programa necessário ausente: {name}; consulte o README")
    xf = Xfconf()
    if args.restore:
        if not MARKER.exists():
            raise RuntimeError("Nenhuma configuração SnoopyOS ativa foi encontrada")
        directory = Path(json.loads(MARKER.read_text())["backup"])
        restore_snapshot(xf, directory)
        print("Área de trabalho anterior restaurada")
        return
    desktop = desktop_path(args.desktop_dir)
    directory = backup(xf, desktop)
    try:
        configure(xf, desktop)
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(json.dumps({"version": VERSION, "backup": str(directory)}, indent=2))
    except Exception:
        print("Falha ao aplicar; restaurando o backup", file=sys.stderr)
        restore_snapshot(xf, directory)
        raise
    print("Área de trabalho SnoopyOS aplicada")
    print(f"Backup: {directory}")
    print("Para desfazer: bash restaurar.sh")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SnoopyOS: {exc}", file=sys.stderr)
        sys.exit(1)
