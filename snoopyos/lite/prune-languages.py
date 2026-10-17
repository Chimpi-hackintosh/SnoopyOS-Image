#!/usr/bin/env python3
"""Mantém traduções em português/inglês e conserva os documentos de licença."""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
locale = root / "usr/share/locale"
removed = 0
for path in sorted(locale.iterdir()):
    if path.is_dir() and not path.is_symlink() and path.name not in ("en", "pt") and not path.name.startswith(("en_", "pt_")):
        shutil.rmtree(path)
        removed += 1
config = root / "etc/dpkg/dpkg.cfg.d/snoopyos-lite-locales"
config.write_text("""# Edição Lite: conserva português e inglês nas próximas instalações
path-exclude=/usr/share/locale/*
path-include=/usr/share/locale/locale.alias
path-include=/usr/share/locale/pt*
path-include=/usr/share/locale/en*
""")
print(f"Diretórios de traduções extras removidos: {removed}")
