#!/bin/bash
# Executar como root em Linux com permissão para chroot e mount
set -euo pipefail
ROOT=$(realpath "$1")
LIST=$(realpath "$2")
REPORT=$(realpath "$3")
POLICY="$ROOT/usr/sbin/policy-rc.d"
if [ -e "$POLICY" ]; then cp -a "$POLICY" "$POLICY.snoopy-backup"; fi
cleanup() {
    rm -f "$POLICY"
    if [ -e "$POLICY.snoopy-backup" ]; then mv "$POLICY.snoopy-backup" "$POLICY"; fi
    umount "$ROOT/tmp" "$ROOT/sys" "$ROOT/proc" "$ROOT/dev/pts" "$ROOT/dev" 2>/dev/null || true
}
trap cleanup EXIT
printf '#!/bin/sh\nexit 101\n' > "$POLICY"
chmod 755 "$POLICY"
mount --bind /dev "$ROOT/dev"
mount --bind /dev/pts "$ROOT/dev/pts"
mount -t proc proc "$ROOT/proc"
mount -t sysfs sysfs "$ROOT/sys"
mount -t tmpfs tmpfs "$ROOT/tmp"
mapfile -t PACKAGES < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))))' "$LIST")
chroot "$ROOT" env LC_ALL=C DEBIAN_FRONTEND=noninteractive apt-get -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache= -y --no-download purge "${PACKAGES[@]}"
chroot "$ROOT" env LC_ALL=C dpkg --audit > "$REPORT/dpkg-audit.txt"
test ! -s "$REPORT/dpkg-audit.txt"
chroot "$ROOT" env LC_ALL=C apt-get -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache= check
for PACKAGE in xfce4 xfce4-terminal thunar firefox-esr calamares lightdm sudo; do
    test "$(chroot "$ROOT" dpkg-query -W -f='${db:Status-Status}' "$PACKAGE")" = installed
done
chroot "$ROOT" dpkg-query -W -f='${Package} ${Version} ${db:Status-Status}\n' |
    awk '$3 == "installed" {print $1, $2}' > "$REPORT/filesystem.packages"
printf 'SNOOPY_PURGE_DONE\n'
