#!/usr/bin/env bash
# Edição Games: reaproveita a receita Lite e inclui widgets GTK
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "Uso: sudo bash snoopyos/games/build.sh BASE-DEBIAN.iso SAIDA-GAMES.iso" >&2
  exit 2
fi
SOURCE=$(cd -- "$(dirname -- "$0")/.." && pwd)
exec bash "$SOURCE/lite/build.sh" "$1" "$2" --games
