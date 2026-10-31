#!/bin/bash
set -euo pipefail
SOURCE=$(cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Uso: sudo bash lite/build.sh BASE.iso SAIDA.iso [--games]" >&2
  exit 2
fi
GAME_FLAGS=()
if [ "${3:-}" = "--games" ]; then
  GAME_FLAGS+=(--games)
elif [ "$#" -eq 3 ]; then
  echo "Opção desconhecida: $3" >&2
  exit 2
fi
BASE=$(realpath "$1")
OUTPUT=$(realpath -m "$2")
test "$(id -u)" = 0 || { echo 'Execute com sudo em Linux'; exit 1; }
test ! -e "$OUTPUT"
EXPECTED=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$SOURCE/remaster/BASE-DEBIAN.json")
printf '%s  %s\n' "$EXPECTED" "$BASE" | sha256sum --check
WORK=$(mktemp -d /tmp/snoopyos-lite.XXXXXXXX)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$(dirname "$OUTPUT")"
xorriso -indev "$BASE" -find /live/filesystem.squashfs -exec report_lba -- > "$WORK/lba.txt" 2>/dev/null
OFFSET=$(python3 -c 'import re,sys; print(int(re.search(r"File data lba:\s*\d+\s*,\s*(\d+)\s*,",open(sys.argv[1]).read())[1])*2048)' "$WORK/lba.txt")
unsquashfs -o "$OFFSET" -d "$WORK/rootfs" -processors 2 -no-xattrs -no-progress "$BASE"
bash "$SOURCE/lite/purge-root.sh" "$WORK/rootfs" "$SOURCE/lite/pacotes-removidos.json" "$WORK" | tee "$(dirname "$OUTPUT")/SnoopyOS-Lite-pacotes.log"
python3 "$SOURCE/lite/prune-languages.py" "$WORK/rootfs"
mksquashfs "$WORK/rootfs" "$WORK/filesystem.squashfs" -noappend -comp xz -b 1M -Xbcj x86 -processors "$(nproc)" -mem 512M -no-xattrs -no-progress
INITRD=$(find "$WORK/rootfs/boot" -maxdepth 1 -type f -name 'initrd.img-*' | head -n 1)
test -n "$INITRD"
python3 "$SOURCE/remasterizar-iso.py" "$BASE" "$OUTPUT" --lite-filesystem "$WORK/filesystem.squashfs" --lite-packages "$WORK/filesystem.packages" --lite-removed "$SOURCE/lite/pacotes-removidos.json" --lite-initrd "$INITRD" "${GAME_FLAGS[@]}"
python3 - "$OUTPUT" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);n=p.stat().st_size
assert n < 2*1024**3, f'Limite excedido: {n} bytes'
print(f'{p.name}: {n} bytes = {n/1024**3:.3f} GiB')
PY

