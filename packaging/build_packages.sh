#!/bin/bash
# Build Windows zip, Debian .deb and Linux tarball into ./dist (or $OUT).
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$SRC/dist}"; mkdir -p "$OUT"
VER="$(python3 -c "import sys; sys.path.insert(0,'$SRC'); import quake_installer as q; print(q.__version__)")"
T="$(mktemp -d)"
COMMON=(quake_installer installer_gui.py installer_cli.py mods mods.example.json README.md
        LICENSE MOD-BIND-REPORT.md requirements.txt)
stage() {  # stage <dir> [extra files...]
  mkdir -p "$1"; local d="$1"; shift
  (cd "$SRC" && cp -r "${COMMON[@]}" "$@" "$d/")
  find "$d" -name __pycache__ -prune -exec rm -rf {} +
}
# Windows (flat tree)
stage "$T/win" tools build_exe.bat run_installer.bat requirements-build.txt
rm -f "$T/win/tools/"render_*.py  # icon generators are only needed when editing icons
rm -f "$OUT/based-quake-installer-source-windows.zip"; (cd "$T/win" && zip -qr "$OUT/based-quake-installer-source-windows.zip" .)

# Linux launcher
LAUNCH='#!/bin/sh
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/installer_gui.py" "$@"'
# Debian package
P="$T/deb"; A="$P/opt/based-quake-installer"
stage "$A"
printf '%s\n' "$LAUNCH" > "$A/run_installer.sh"; chmod 755 "$A/run_installer.sh"
mkdir -p "$P/usr/bin" "$P/usr/share/applications" "$P/DEBIAN"
printf '#!/bin/sh\nexec python3 /opt/based-quake-installer/installer_gui.py "$@"\n' > "$P/usr/bin/based-quake-installer"
chmod 755 "$P/usr/bin/based-quake-installer"
cat > "$P/usr/share/applications/based-quake-installer.desktop" <<D
[Desktop Entry]
Type=Application
Name=Based Quake Installer
Comment=Install unezQuake + FTE + Quake mods
Exec=based-quake-installer
Terminal=false
Categories=Game;
D
cat > "$P/DEBIAN/control" <<C
Package: based-quake-installer
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-tk
Maintainer: USDQC
Description: installer for the unezQuake and FTE Quake clients and mods
 GUI installer for the unezQuake and FTE QuakeWorld clients plus classic
 Quake mods. Writes per-client configs and key binds, and can check for
 client and mod updates.
C
D="$P/usr/share/doc/based-quake-installer"; mkdir -p "$D"
cat > "$D/copyright" <<CR
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: based-quake-installer

Files: *
Copyright: 2026 USDQC
License: GPL-3.0-or-later
Comment: unezQuake, FTE, the Quake shareware data and the mods are downloaded at
 install time and keep their own licences; none of them are in this package.

License: GPL-3.0-or-later
 This program is free software: you can redistribute it and/or modify it under
 the terms of the GNU General Public License as published by the Free Software
 Foundation, either version 3 of the License, or (at your option) any later
 version.
 .
 This program is distributed in the hope that it will be useful, but WITHOUT ANY
 WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 PARTICULAR PURPOSE. See the GNU General Public License for more details.
 .
 On Debian systems, the full text of the GNU General Public License version 3
 can be found in /usr/share/common-licenses/GPL-3.
CR
printf 'based-quake-installer (%s) unstable; urgency=low\n\n  * Release %s.\n\n -- USDQC  %s\n' \
  "$VER" "$VER" "$(date -R)" | gzip -9n > "$D/changelog.gz"
find "$P" -type d -exec chmod 755 {} +
DEB="$OUT/based-quake-installer_${VER}_all.deb"
dpkg-deb --root-owner-group --build "$P" "$DEB" >/dev/null
# Linux tarball
L="$T/lin/based-quake-installer"; stage "$L"
printf '%s\n' "$LAUNCH" > "$L/run_installer.sh"; chmod 755 "$L/run_installer.sh"
tar -C "$T/lin" -czf "$OUT/based-quake-installer-linux.tar.gz" based-quake-installer
rm -rf "$T"
ls -l "$OUT/based-quake-installer-source-windows.zip" "$DEB" \
      "$OUT/based-quake-installer-linux.tar.gz"
