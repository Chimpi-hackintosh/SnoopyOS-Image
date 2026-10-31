#!/usr/bin/env python3
"""Personaliza uma ISO Debian Live verificada, preservando o boot BIOS/UEFI."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
PARAMETERS = "locales=pt_BR.UTF-8 keyboard-layouts=br timezone=America/Sao_Paulo username=snoopy hostname=snoopyos"


def digest(path, algorithm="sha256"):
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def command(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("saida", type=Path)
    parser.add_argument("--lite-filesystem", type=Path, help="SquashFS reduzido com dpkg consistente")
    parser.add_argument("--lite-packages", type=Path, help="Manifesto dpkg-query da edição Lite")
    parser.add_argument("--lite-removed", type=Path, help="Lista JSON dos pacotes removidos")
    parser.add_argument("--lite-initrd", type=Path, help="Initramfs regenerado depois da redução")
    parser.add_argument("--games", action="store_true", help="Gerar SnoopyOS Games com painel de jogos")
    args = parser.parse_args()
    lite = args.lite_filesystem is not None
    if lite != (args.lite_packages is not None):
        parser.error("--lite-filesystem e --lite-packages devem ser usados juntos")
    if args.games and not lite:
        parser.error("--games exige a receita Lite com filesystem e manifesto")
    edition = "0.2 Games Preview" if args.games else ("0.1 Lite Preview" if lite else "0.1 Preview")
    short_version = "0.2" if args.games else "0.1"
    boot_parameters = PARAMETERS + (" console=tty0 console=ttyS0,115200n8" if lite else "")
    base, output = args.base.resolve(), args.saida.resolve()
    for name in ("xorriso", "unsquashfs", "mksquashfs"):
        if not shutil.which(name):
            raise RuntimeError("Ferramenta necessária ausente: " + name)
    if output.exists():
        raise RuntimeError("O arquivo de saída já existe; use outro nome")
    metadata = json.loads((ROOT / "remaster/BASE-DEBIAN.json").read_text())
    print("Conferindo SHA-256 da base", flush=True)
    accepted = {metadata["sha256"]}
    if lite:
        accepted.add("860489f9bab59e9d563bbbefc059149f23bb4bb744a655155c4f3df6358fb96f")
    if digest(base) not in accepted:
        raise RuntimeError("A base não corresponde à imagem Debian registrada")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="snoopyos-build-", dir=output.parent) as name:
        work = Path(name)
        report = command(["xorriso", "-indev", str(base), "-find",
                          "/live/filesystem.squashfs", "-exec", "report_lba", "--"])
        match = re.search(r"File data lba:\s*\d+\s*,\s*(\d+)\s*,", report)
        if not match:
            raise RuntimeError("Não foi encontrado o sistema de arquivos da base")
        offset = str(int(match.group(1)) * 2048)

        def root_text(path):
            return command(["unsquashfs", "-o", offset, "-cat", str(base), path])

        def extract(path):
            destination = work / (path.strip("/").replace("/", "__"))
            command(["xorriso", "-osirrox", "on", "-indev", str(base),
                     "-extract", path, str(destination)])
            destination.chmod(0o644)
            return destination

        overlay = work / "overlay"
        overlay.mkdir()

        def write(path, contents):
            destination = overlay / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(contents)
            return destination

        print("Preparando a personalização do sistema e do instalador", flush=True)
        shutil.copytree(ROOT / "desktop", overlay / "usr/share/snoopyos")
        if args.games:
            shutil.copy2(ROOT / "games/games.py", overlay / "usr/share/snoopyos/games.py")
            write("etc/skel/.config/autostart/snoopyos-games.desktop", """[Desktop Entry]
Type=Application
Name=SnoopyOS Games Widgets
Comment=Painel leve de CPU, RAM, disco e modo FPS
Exec=/usr/bin/python3 /usr/share/snoopyos/games.py widget
OnlyShowIn=XFCE;
Terminal=false
X-GNOME-Autostart-enabled=true
""")
            write("usr/share/applications/snoopyos-games.desktop", """[Desktop Entry]
Type=Application
Name=SnoopyOS Games
Comment=Painel gamer com widgets leves
Exec=/usr/bin/python3 /usr/share/snoopyos/games.py widget
Icon=/usr/share/snoopyos/assets/snoopy-menu.svg
Terminal=false
Categories=Game;Utility;
""")
        write("etc/skel/.config/autostart/snoopyos-primeiro-login.desktop", """[Desktop Entry]
Type=Application
Name=Configurar a área de trabalho SnoopyOS
Exec=/usr/bin/python3 /usr/share/snoopyos/aplicar.py --autostart
OnlyShowIn=XFCE;
Terminal=false
StartupNotify=false
""")
        write("etc/skel/.dmrc", "[Desktop]\nSession=xfce\n")
        write("etc/xdg/autostart/calamares-desktop-icon.desktop", """[Desktop Entry]
Type=Application
Name=Installer desktop icon
Hidden=true
""")
        installer = root_text("usr/share/applications/calamares-install-debian.desktop")
        installer = re.sub(r'^Name=.*$', 'Name=Install SnoopyOS', installer, flags=re.M)
        installer += '\nName[pt_BR]=Instalar SnoopyOS\nName[pt]=Instalar SnoopyOS\n'
        installer = re.sub(r'^Icon=.*$', 'Icon=/usr/share/snoopyos/assets/snoopy-menu.svg', installer, flags=re.M)
        write("usr/share/applications/calamares-install-debian.desktop", installer)
        release = root_text("etc/os-release")
        release = re.sub(r'^PRETTY_NAME=.*$', f'PRETTY_NAME="SnoopyOS {edition} (Debian 13.7)"', release, flags=re.M)
        release = re.sub(r'^NAME=.*$', 'NAME="SnoopyOS"', release, flags=re.M)
        release += f'\nVARIANT="SnoopyOS {edition}"\nVARIANT_ID=snoopyos\n'
        write("etc/os-release", release)
        write("usr/share/doc/snoopyos/README.md", """# SnoopyOS 0.1 Preview

Base Debian 13.7 amd64 com Xfce/X11 e personalização SnoopyOS

O menu Snoopy + abre os aplicativos e o Terminal está disponível na barra e na área de trabalho

Atalhos: Ctrl + Alt + T abre o Terminal e Super abre o menu

O ambiente live utiliza o usuário snoopy e não preserva alterações após desligar sem persistência ou instalação

O instalador Calamares foi configurado para copiar a base e a camada de personalização

Esta edição é uma prévia de desenvolvimento
""")
        if args.games:
            readme_path = overlay / "usr/share/doc/snoopyos/README.md"
            readme_path.write_text(readme_path.read_text().replace("0.1 Preview", edition) + """
SnoopyOS Games oferece widgets leves, indicador de RAM/CPU e modo FPS reversível
Abra SnoopyOS Games no menu e execute jogos pelo lançador para limpeza segura
A limpeza não remove arquivos pessoais, saves nem os caches do Steam
O desempenho e FPS real dependem dos jogos, drivers e hardware
""")
        if lite:
            readme_path = overlay / "usr/share/doc/snoopyos/README.md"
            readme_path.write_text(readme_path.read_text().replace("0.1 Preview", edition) + """
Edição Lite: imagem abaixo de 2 GiB, sem LibreOffice, fontes extras e métodos de entrada IBus

Mantém Xfce, Terminal, Thunar, Firefox, áudio, rede e instalador Calamares

Firmwares adicionais de gráficos, áudio e algumas redes foram removidos para reduzir o tamanho
As placas Intel Wi-Fi, Realtek e Atheros mantêm seus pacotes básicos de firmware
Outros equipamentos podem exigir a instalação manual do firmware correspondente
""")
        settings = root_text("etc/calamares/settings.conf")
        if "branding: debian" not in settings:
            raise RuntimeError("A configuração do instalador da base mudou")
        write("etc/calamares/settings.conf", settings.replace("branding: debian", "branding: snoopyos"))
        write("etc/calamares/modules/unpackfs.conf", """---
unpack:
    - source: "/run/live/medium/live/filesystem.squashfs"
      sourcefs: "squashfs"
      destination: ""
    - source: "/run/live/medium/live/zz-snoopyos.squashfs"
      sourcefs: "squashfs"
      destination: ""
""")
        branding = root_text("etc/calamares/branding/debian/branding.desc")
        replacements = {"componentName": "snoopyos", "productName": "SnoopyOS",
                        "shortProductName": "SnoopyOS", "version": edition,
                        "shortVersion": short_version, "versionedName": "SnoopyOS " + edition,
                        "shortVersionedName": "SnoopyOS " + short_version, "bootloaderEntryName": "SnoopyOS"}
        for key, value in replacements.items():
            branding = re.sub(rf"^(\s*{key}:)\s*.*$", rf"\1 {value}", branding, flags=re.M)
        branding = re.sub(r"^\s*donateUrl:.*\n", "", branding, flags=re.M)
        branddir = "etc/calamares/branding/snoopyos/"
        write(branddir + "branding.desc", branding)
        write(branddir + "show.qml", root_text("etc/calamares/branding/debian/show.qml"))
        for image in ["debian-logo.png", "welcome.png", "slide1.png"]:
            target = overlay / branddir / image
            shutil.copy2(ROOT / "remaster/branding" / image, target)

        layer = work / "zz-snoopyos.squashfs"
        command(["mksquashfs", str(overlay), str(layer), "-all-root", "-noappend",
                 "-comp", "xz", "-b", "1M", "-processors", "2", "-no-progress"])
        listing = command(["unsquashfs", "-ls", str(layer)])
        if "usr/share/snoopyos/aplicar.py" not in listing:
            raise RuntimeError("A camada personalizada está incompleta")

        grub = extract("/boot/grub/grub.cfg")
        original_grub = grub.read_text()
        first = re.search(r'menuentry "(?:Live system \(amd64\)|Iniciar SnoopyOS 0.1 \(64 bits\))".*?\n}', original_grub, re.S)
        failsafe = re.search(r'menuentry "(?:Live system \(amd64 fail-safe mode\)|SnoopyOS - modo de compatibilidade)".*?\n}', original_grub, re.S)
        if not first or not failsafe:
            raise RuntimeError("O menu de boot da base mudou")
        boot_label = "Iniciar SnoopyOS " + ("0.2 Games" if args.games else ("0.1 Lite" if lite else "0.1")) + " (64 bits)"
        normal = re.sub(r'^menuentry "[^"]*"', 'menuentry "' + boot_label + '"', first.group(0))
        safe = failsafe.group(0).replace('"Live system (amd64 fail-safe mode)"', '"SnoopyOS - modo de compatibilidade"')
        def parameters(text):
            return "\n".join(line.replace(" " + PARAMETERS, "") + " " + boot_parameters if re.match(r"\s*linux\s+/live/", line) else line
                             for line in text.splitlines())
        grub.write_text("source /boot/grub/config.cfg\nset default=0\nset timeout=5\n\n" +
                        parameters(normal) + "\n\n" + parameters(safe) + "\n")
        live = extract("/isolinux/live.cfg")
        text = live.read_text().replace("^Live system (amd64)", "^Iniciar SnoopyOS 0.1 (64 bits)")
        text = text.replace("Live system (amd64 fail-safe mode)", "SnoopyOS - modo de compatibilidade")
        if args.games:
            text = text.replace("Iniciar SnoopyOS 0.1 (64 bits)", "Iniciar SnoopyOS 0.2 Games (64 bits)")
        elif lite:
            text = text.replace("Iniciar SnoopyOS 0.1 (64 bits)", "Iniciar SnoopyOS 0.1 Lite (64 bits)")
        live.write_text("\n".join(line.replace(" " + PARAMETERS, "") + " " + boot_parameters if line.strip().startswith("append ") else line
                                  for line in text.splitlines()) + "\n")
        menu = extract("/isolinux/menu.cfg")
        menu.write_text(menu.read_text().replace("menu title Boot menu\x07", "menu title SnoopyOS " + edition)
                        .replace("menu title SnoopyOS 0.1 Preview", "menu title SnoopyOS " + edition)
                        .replace("include install.cfg\n", ""))
        isolinux = extract("/isolinux/isolinux.cfg")
        isolinux.write_text("include menu.cfg\ndefault vesamenu.c32\nprompt 0\ntimeout 50\n")
        module = work / "filesystem.module"
        module.write_text("filesystem.squashfs\nzz-snoopyos.squashfs\n")
        info = work / "info"
        info.write_text("SnoopyOS " + edition + " - based on Debian GNU/Linux Live 13.7.0 xfce\n")
        readme = work / "README-SnoopyOS.md"
        shutil.copy2(overlay / "usr/share/doc/snoopyos/README.md", readme)
        mappings = {"/boot/grub/grub.cfg": grub, "/isolinux/live.cfg": live,
                    "/isolinux/menu.cfg": menu, "/isolinux/isolinux.cfg": isolinux,
                    "/live/filesystem.module": module, "/live/zz-snoopyos.squashfs": layer,
                    "/.disk/info": info, "/README-SnoopyOS.md": readme,
                    "/isolinux/splash.png": ROOT / "remaster/branding/boot-splash.png"}
        removed_paths = []
        if lite:
            removed_paths = ["/install", "/pool-udeb", "/firmware",
                             "/pool/non-free-firmware", "/pool/main/l/linux-signed-amd64",
                             "/dists/trixie/main/debian-installer", "/dists/trixie/non-free-firmware"]
            mappings["/live/filesystem.squashfs"] = args.lite_filesystem.resolve()
            mappings["/live/filesystem.packages"] = args.lite_packages.resolve()
            if args.lite_initrd:
                live_files = command(["xorriso", "-indev", str(base), "-find", "/live", "-type", "f", "-exec", "report_lba", "--"])
                initrd_paths = re.findall(r"'(/live/initrd\.img[^']*)'", live_files)
                if not initrd_paths:
                    raise RuntimeError("Initramfs da base não encontrado")
                for path in initrd_paths:
                    mappings[path] = args.lite_initrd.resolve()
            if args.lite_removed:
                mappings["/PACOTES-REMOVIDOS.json"] = args.lite_removed.resolve()
            # Conserva o repositório local usado pelo Calamares para instalar GRUB
            packages = extract("/dists/trixie/main/binary-amd64/Packages")
            blocks = packages.read_text().strip().split("\n\n")
            blocks = [block for block in blocks if not re.search(
                r'^Filename: pool/main/l/linux-signed-amd64/', block, re.M)]
            packages.write_text("\n\n".join(blocks) + "\n\n")
            packages_gz = work / "Packages.gz"
            packages_gz.write_bytes(gzip.compress(packages.read_bytes(), mtime=0))
            binary_release = extract("/dists/trixie/main/binary-amd64/Release")
            indexes = {"main/binary-amd64/Packages": packages,
                       "main/binary-amd64/Packages.gz": packages_gz,
                       "main/binary-amd64/Release": binary_release}
            dist_release = work / "Release"
            content = "Origin: SnoopyOS\nLabel: SnoopyOS Lite\nSuite: stable\nCodename: trixie\nArchitectures: amd64\nComponents: main\nDescription: SnoopyOS Lite installation packages\n"
            for title, algorithm in [("MD5Sum", "md5"), ("SHA256", "sha256")]:
                content += title + ":\n"
                for path, source in indexes.items():
                    content += f" {digest(source, algorithm)} {source.stat().st_size:16d} {path}\n"
            dist_release.write_text(content)
            for path, source in indexes.items():
                mappings["/dists/trixie/" + path] = source
            mappings["/dists/trixie/Release"] = dist_release
        def removed(path):
            absolute = path.removeprefix(".")
            return any(absolute == prefix or absolute.startswith(prefix + "/") for prefix in removed_paths)
        sums = extract("/md5sum.txt")
        entries = {}
        for line in sums.read_text().splitlines():
            checksum, path = line.split(None, 1)
            if not removed(path) and path not in ("./md5sum.txt", "./sha256sum.txt"):
                entries[path] = checksum
        for path, source in mappings.items():
            entries["." + path] = digest(source, "md5")
        sums.write_text("".join(value + "  " + key + "\n" for key, value in sorted(entries.items())))
        mappings["/md5sum.txt"] = sums
        sha_sums = extract("/sha256sum.txt")
        sha_entries = {}
        for line in sha_sums.read_text().splitlines():
            checksum, path = line.split(None, 1)
            if not removed(path) and path not in ("./md5sum.txt", "./sha256sum.txt"):
                sha_entries[path] = checksum
        for path, source in mappings.items():
            if path == "/md5sum.txt":
                continue
            sha_entries["." + path] = digest(source)
        sha_sums.write_text("".join(value + "  " + key + "\n" for key, value in sorted(sha_entries.items())))
        mappings["/sha256sum.txt"] = sha_sums
        # Mantém o UUID ISO usado pelos arquivos de boot assinados da base
        with base.open("rb") as stream:
            stream.seek(16 * 2048 + 813)
            volume_date = stream.read(16).decode("ascii")
        cmd = ["xorriso", "-indev", str(base), "-outdev", str(output),
               "-hardlinks", "on",
               "-boot_image", "any", "replay", "-volid", "SNOOPYOSLITE" if lite else "SNOOPYOS01",
               "-volume_date", "uuid", volume_date]
        for path in removed_paths:
            cmd += ["-rm_r", path, "--"]
        for path, source in mappings.items():
            cmd += ["-map", str(source), path]
        print("Gravando a ISO híbrida SnoopyOS", flush=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        (output.parent / "SnoopyOS-montagem.log").write_text(result.stdout + "\n" + result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr)
    print("Conferindo a imagem gerada", flush=True)
    report = command(["xorriso", "-indev", str(output), "-report_el_torito", "plain",
                      "-report_system_area", "plain"])
    if "BIOS" not in report or "UEFI" not in report:
        raise RuntimeError("O catálogo de boot não contém BIOS e UEFI")
    if lite and output.stat().st_size >= 2 * 1024**3:
        raise RuntimeError(f"A ISO excedeu o limite: {output.stat().st_size} bytes (máximo 2147483647)")
    (output.parent / "SnoopyOS-boot.txt").write_text(report)
    checksum = digest(output)
    (output.parent / "SHA256SUMS.txt").write_text(checksum + "  " + output.name + "\n")
    print("ISO criada: " + str(output), flush=True)
    print("SHA256: " + checksum, flush=True)


if __name__ == "__main__":
    main()

