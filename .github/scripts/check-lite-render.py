#!/usr/bin/env python3
"""Inicia a ISO em UEFI, verifica o Xfce personalizado e o atalho do Terminal."""
import base64
import json
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time

iso = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="snoopyos-boot-") as temporary:
    work = Path(temporary)
    shutil.copy2("/usr/share/OVMF/OVMF_VARS_4M.fd", work / "vars.fd")
    command = ["qemu-system-x86_64", "-accel", "tcg,thread=multi", "-smp", "2", "-m", "3072",
               "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
               "-drive", f"if=pflash,format=raw,file={work / 'vars.fd'}", "-cdrom", str(iso),
               "-boot", "order=d", "-display", "none", "-nic", "none",
               "-chardev", f"socket,id=serial,path={work / 'serial.sock'},server=on,wait=off",
               "-serial", "chardev:serial", "-qmp", f"unix:{work / 'qmp.sock'},server=on,wait=off"]
    with (output / "QEMU-boot.log").open("wb") as error, (output / "SnoopyOS-serial.log").open("wb") as serial_log:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=error)
        connections = []
        try:
            def connect(name):
                sock = socket.socket(socket.AF_UNIX)
                deadline = time.monotonic() + 30
                while True:
                    try:
                        sock.connect(str(work / name))
                        connections.append(sock)
                        return sock
                    except (FileNotFoundError, ConnectionRefusedError):
                        if time.monotonic() > deadline or process.poll() is not None:
                            raise RuntimeError("QEMU não abriu " + name)
                        time.sleep(0.2)

            serial = connect("serial.sock")
            qmp = connect("qmp.sock")
            qmp.settimeout(30)
            monitor = qmp.makefile("rwb")
            json.loads(monitor.readline())

            def execute(name, arguments=None):
                request = {"execute": name}
                if arguments is not None:
                    request["arguments"] = arguments
                monitor.write((json.dumps(request) + "\n").encode())
                monitor.flush()
                while True:
                    response = json.loads(monitor.readline())
                    if "error" in response:
                        raise RuntimeError(str(response["error"]))
                    if "return" in response:
                        return response["return"]

            execute("qmp_capabilities")
            buffer = b""

            def wait_for(pattern, seconds):
                global buffer
                deadline = time.monotonic() + seconds
                notice = time.monotonic() + 30
                expression = re.compile(pattern)
                while time.monotonic() < deadline:
                    if expression.search(buffer):
                        buffer = b""
                        return
                    if process.poll() is not None:
                        raise RuntimeError("QEMU encerrou durante o boot")
                    if select.select([serial], [], [], 1)[0]:
                        block = serial.recv(65536)
                        if not block:
                            raise RuntimeError("Console serial encerrado")
                        serial_log.write(block)
                        serial_log.flush()
                        buffer = (buffer + block)[-256000:]
                    if time.monotonic() >= notice:
                        print("Aguardando a etapa de boot: " + pattern.decode(), flush=True)
                        notice = time.monotonic() + 30
                raise RuntimeError("Tempo excedido: " + pattern.decode())

            def shell(script):
                data = base64.b64encode(script.encode()).decode()
                serial.sendall(("printf %s " + data + " | base64 -d | sudo -n bash\n").encode())

            wait_for(rb"login: ", 900)
            serial.sendall(b"snoopy\n")
            wait_for(rb"(?:Password|Senha):", 60)
            serial.sendall(b"live\n")
            wait_for(rb"snoopy@[^\r\n]*\$", 60)
            shell("""set -e
grep -q 'SnoopyOS 0.1 Lite' /etc/os-release
test -z "$(dpkg --audit)"
apt-get -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache= check
for app in xfce4-terminal thunar firefox-esr calamares; do command -v "$app"; done
for i in $(seq 1 240); do
    if pgrep -u snoopy -x xfce4-panel >/dev/null && test -s /home/snoopy/.local/state/snoopyos/layout.json && grep -R -q 'papel-de-parede.svg' /home/snoopy/.config/xfce4; then break; fi
    sleep 2
done
pgrep -u snoopy -x xfce4-panel
pgrep -u snoopy -x xfdesktop
test -s /home/snoopy/.local/state/snoopyos/layout.json
grep -R -q 'papel-de-parede.svg' /home/snoopy/.config/xfce4
printf 'SNOOPY_DESKTOP_OK\\n'
""")
            wait_for(rb"SNOOPY_DESKTOP_OK", 600)
            execute("human-monitor-command", {"command-line": "sendkey ctrl-alt-t"})
            shell("""set -e
for i in $(seq 1 60); do
    if pgrep -u snoopy -x xfce4-terminal >/dev/null; then printf 'SNOOPY_TERMINAL_OK\\n'; exit 0; fi
    sleep 1
done
exit 1
""")
            wait_for(rb"SNOOPY_TERMINAL_OK", 90)
            time.sleep(3)
            from PIL import Image
            def screenshot(name):
                ppm = work / "screen.ppm"
                execute("screendump", {"filename": str(ppm)})
                Image.open(ppm).save(output / name)
            deadline = time.monotonic() + 240
            while True:
                screenshot("SnoopyOS-Lite-last-frame.png")
                frame = Image.open(output / "SnoopyOS-Lite-last-frame.png").convert("RGB")
                pixels = list(frame.resize((160, 100)).getdata())
                blue = sum(r < 80 and g > 100 and b > 180 for r, g, b in pixels) / len(pixels)
                green = sum(r < 90 and g > 200 and 80 < b < 220 for r, g, b in pixels) / len(pixels)
                footer = list(frame.crop((0, frame.height - 70, frame.width, frame.height)).resize((160, 10)).getdata())
                cream = sum(r > 220 and g > 210 and 120 < b < 220 for r, g, b in footer) / len(footer)
                print(f"Renderização: azul={blue:.3f}, verde={green:.3f}, barra={cream:.3f}", flush=True)
                if blue > 0.15 and green > 0.01 and cream > 0.55:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("O papel de parede e a barra ainda não foram renderizados")
                time.sleep(5)
            execute("human-monitor-command", {"command-line": "sendkey ctrl-alt-t"})
            time.sleep(20)
            screenshot("SnoopyOS-Lite-desktop.png")
            execute("human-monitor-command", {"command-line": "sendkey meta_l"})
            time.sleep(15)
            screenshot("SnoopyOS-Lite-menu.png")
            (output / "SnoopyOS-validacao.json").write_text(json.dumps({
                "uefiBoot": True, "desktop": "Xfce", "customization": True,
                "terminalShortcut": True, "renderedWallpaper": True, "panelVisible": True, "dpkgAudit": "passed", "aptCheck": "passed",
                "diskInstallationTested": False
            }, indent=2) + "\n")
            print("Boot UEFI, Xfce personalizado e Terminal verificados", flush=True)
            execute("quit")
        finally:
            for connection in connections:
                connection.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
