# Based Quake Installer

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

A one-click installer that sets up a complete, ready-to-play **QuakeWorld** setup on
**Windows 10/11 x64** and **Debian-based Linux** (Debian, Ubuntu, Pop!_OS, Mint):

- two modern clients, **unezQuake** and **FTE**, each in its own folder,
- the official Quake **shareware** data (`pak0.pak`) in both,
- ten classic **mods** (Team Fortress, CTF, Rocket Arena and more),
- your **name, look and key binds** written into every client and mod,
- a working **server browser** list for unezQuake,
- and a **Check for updates** button that keeps it all current.

On Windows it's a single standalone `.exe`, so **no Python needed**. It's written in Python 3 with the standard
library's tkinter, and the exe is built from this repo by GitHub Actions.
It's an installer only: it doesn't launch games, create `.bat` files or shortcuts, or use Slipgate or other
launchers. When it finishes, you start `unezquake.exe` or `fteqw64.exe` yourself and pick a mod with `-game`.

## Features

- **Both clients, separate trees.** `{root}/unezQuake/` and `{root}/FTE/`, each with its own `id1`,
  configs and mods. The installer always downloads the builds for the OS it's running on.
- **Shareware data done right.** `quake106.zip` comes from public id Software mirrors (three of them).
  `pak0.pak` is extracted with the bundled 7-Zip on Windows, or the built-in pure-Python LH5 decoder,
  and MD5-checked (`5906e5998fc3d896ddaf5e6a62e03abb`). It never ships any `.pak` files.
- **All mods, always installed**, into the client(s) each one works with:

  | Mod | `-game` folder | Clients | Registered Quake (`pak1.pak`)? |
  |---|---|---|---|
  | AirQuake 1.03 | `airquake` | **FTE only** | no |
  | PainKeep 1.11 | `painkeep` | unezQuake + FTE | yes |
  | Headhunters 3.0 (client) | `hh` | unezQuake + FTE | yes |
  | Team Fortress 2.8 + 2.9 QW | `fortress` | unezQuake + FTE | yes |
  | Thunderwalker CTF (ThreeWave + TW 3.01) | `ctf` | unezQuake + FTE | yes |
  | Rocket Arena (Final Arena 1.2) | `arena` | unezQuake + FTE | no |
  | Future vs Fantasy 4 (client pak 2.09.21) | `fvf` | **FTE only** | yes |
  | Quake Rally 1.2 + Leftovers | `rally` | **FTE only** | yes |
  | Get Rich Quake 1.1 | `grq` | unezQuake + FTE | yes |
  | Rune Quake | `runequake` | unezQuake + FTE | no (server-side mod, nothing downloaded) |

  Each mod is a single pre-built zip on the USDQC Google Drive (patches applied, names lowercase),
  checked against the **sha256** in `mods.json` before anything is unzipped. A mismatch installs nothing.
  For the mods marked "yes", copy your own legal `pak1.pak` into that client's `id1` folder.
- **Binds editor.** Classic QuakeWorld "Customize Controls" plus weapon keys, with **Default** (stock
  `default.cfg`) and **Clear** presets. A **Mod binds** tab adds optional per-mod commands (Team Fortress
  grenades, CTF grapple, Arena, PainKeep, AirQuake, Rally, Get Rich Quake, Rune Quake) as `binds.cfg` in
  that mod's folder. Your name, binds and **Software / OpenGL look** go into `id1/based.cfg`, and every mod's
  `autoexec.cfg` runs `exec based.cfg`, so your setup works in every `-game`. Your last settings are remembered.
- **FTE without a home directory.** `FTE/default.fmf` gets `DISABLEHOMEDIR 1` (the engine-side `-nohome`),
  so configs and downloads stay inside the FTE folder.
- **Server browser that works out of the box.** unezQuake gets `ezquake/sb/sources.txt` with live sources
  (QuakeServers.net, Asgaard, QuakeWorld.nu masters, plus the quakeservers.net server list), ticked by
  `sb_sourcemark` lines in `based.cfg`. Existing entries are kept (merge, never wipe; `.bak` on change).
- **Check for updates / Update.** Compares the install with `based-quake-manifest.json`: unezQuake against
  its latest GitHub release, FTE against the newest fteqw.org build date, mods against `mods.json`
  (version + sha256). **Update** replaces only what's outdated and keeps your `autoexec.cfg`, `binds.cfg`,
  `config.cfg`, `fte.cfg` and `default.fmf`. Installs from 1.6.2 or older re-download the mods once.
- **Headless CLI** with the same engine (`installer_cli.py`).

## Download

Get the latest version from the **[Releases page](https://github.com/USDQC/based-quake-installer/releases)**:

| File | For |
|---|---|
| **`BasedQuakeInstaller-windows-x64.zip`** | **Windows 10/11 x64**: standalone `BasedQuakeInstaller.exe`, no Python needed |
| `based-quake-installer_<version>_all.deb` | Debian / Ubuntu / Pop!_OS / Mint |
| `based-quake-installer-linux.tar.gz` | other Linux x64 (run from the folder) |
| `Based-Quake-Installer-Manual.pdf` | the full user manual |
| `based-quake-installer-source-windows.zip` | Windows, run from source with your own Python 3.8+ (`run_installer.bat`) |

## Install

### Windows 10 / 11 (x64)

1. Download **`BasedQuakeInstaller-windows-x64.zip`** from the [latest release](https://github.com/USDQC/based-quake-installer/releases/latest)
   and unzip it.
2. **Double-click `BasedQuakeInstaller.exe`.** No Python or anything else needed.
3. The exe isn't code-signed, so SmartScreen may say *"Windows protected your PC"*. Click **More info → Run anyway**.
4. Pick an install folder (default `C:\Games`), enter your name, choose your binds and look, and click **Install**.

The exe never writes next to itself, so it can live anywhere (even `C:\Program Files`). Settings are kept in
`%APPDATA%\BasedQuakeInstaller\settings.json`. To run from source instead, use
`based-quake-installer-source-windows.zip` with 64-bit Python 3.8+ (keep "tcl/tk and IDLE" ticked) and
double-click `run_installer.bat`.

### Debian / Ubuntu / Pop!_OS / Mint

```bash
sudo apt install ./based-quake-installer_1.6.4_all.deb   # depends on python3, python3-tk
based-quake-installer                                     # or "Based Quake Installer" in the app menu
```

The package installs to `/opt/based-quake-installer` with a `/usr/bin/based-quake-installer` launcher and
a menu entry. The default install folder is `~/Games`. On other distros, unpack
`based-quake-installer-linux.tar.gz` and run `./based-quake-installer/run_installer.sh` (needs Python 3 with tkinter).

Then start a client from its folder, for example:

```bash
~/Games/unezQuake/unezQuake-x86_64.AppImage -game fortress
~/Games/FTE/fteqw64 -game airquake
```

## Run from source

```bash
git clone https://github.com/USDQC/based-quake-installer.git
cd based-quake-installer
python3 installer_gui.py          # Windows: python installer_gui.py, or run_installer.bat
```

Command-line installs use the same engine:

```bash
python3 installer_cli.py --root ~/Games --name Ranger --preset wasd --look gl
python3 installer_cli.py --root ~/Games --check-updates
python3 installer_cli.py --version             # or --self-test
python3 installer_cli.py --root ~/Games --update
python3 installer_cli.py --root ~/Games --mods fortress,ctf --mods-only
python3 installer_cli.py --root ~/Games --mods fortress --mods-only --mod-file fortress=~/Downloads/fortress.zip
```

`--preset` is `vanilla` (stock `default.cfg`, the default), `wasd`, `modern` (WASD + modern weapon keys) or
`none`. `--mod-file KEY=PATH` installs a Drive zip you already downloaded; it's still sha256-checked.
`python3 installer_cli.py --help` lists everything.

### Tests

```bash
python3 -m pip install pytest
python3 -m pytest -q tests
```

## Build

- **Release packages** (Windows zip, `.deb`, Linux tarball), on a Debian-based box with `dpkg-deb`:

  ```bash
  OUT=dist bash packaging/build_packages.sh
  ```

- **Windows .exe**: `build_exe.bat` on Windows with 64-bit Python 3.8+ builds `dist\BasedQuakeInstaller.exe`
  (one file, windowed) and `dist\BasedQuakeInstaller-cli.exe`, using the PyInstaller version pinned in
  `requirements-build.txt`. `tools\7za.exe` is bundled and found through `sys._MEIPASS`.
  `BasedQuakeInstaller-cli.exe --self-test` checks a build. The
  [`windows-exe` workflow](.github/workflows/windows-exe.yml) runs the same script on `windows-latest`
  for every published release (or by hand with a tag), runs the tests and self-tests, and uploads
  `BasedQuakeInstaller-windows-x64.zip` to the release.
- **Mod zips for Google Drive**: `packaging/drive/build_drive_zips.py <staged gamedirs> <out>` builds one
  `<gamedir>.zip` per mod plus `mods.json` (sizes and sha256). See `packaging/drive/` for the upload steps.
- **Manual**: `manual/Based-Quake-Installer-Manual.md` → PDF with `manual/build_pdf.py` (needs `markdown`
  and `weasyprint`).

## Where the downloads come from

Nothing below is bundled. Everything is downloaded over HTTPS at install time, from:

| Component | Source |
|---|---|
| **unezQuake** | latest release of [dusty-qw/unezquake](https://github.com/dusty-qw/unezquake/releases) on GitHub (falls back to the 2.1.1 assets if the API is unreachable) |
| **FTE** | the newest dated build linked from [fteqw.org](https://www.fteqw.org/) (`fastdl.idtech.space`); a pinned official build is the fallback |
| **Quake shareware** | id Software's `quake106.zip` from public mirrors, MD5-checked |
| **Mods** | the USDQC Google Drive, via `mods.json` (one zip per mod, sha256-checked) |

The `mods.json` link is `MODS_INDEX_URL` in `quake_installer/constants.py`. You can override it with
`BASED_QUAKE_MODS_INDEX=<url>`, or with a `mods.json` next to `installer_gui.py` (format:
`mods.example.json`). The built-in table in `quake_installer/mods.py` is the last fallback.

## Project layout

```
installer_gui.py / installer_cli.py   GUI and CLI entry points
run_installer.bat / build_exe.bat     Windows launcher and PyInstaller build
quake_installer/                      the engine: downloads (incl. Google Drive), extraction, LH5 decoder,
                                      clients, mods, configs and binds, sources.txt, manifest, updater, GUI
tests/                                pytest suite
packaging/                            build_packages.sh (source zip/.deb/tar.gz) and drive/ (mod zip builder)
.github/workflows/windows-exe.yml     builds and uploads the Windows exe for each release
manual/                               user manual source, screenshots and PDF builder
tools/7za.exe                         7-Zip 9.20 command-line (Windows), see below
```

## Credits

- **unezQuake** by the ezQuake / unezQuake developers: <https://github.com/dusty-qw/unezquake>
- **FTE QuakeWorld** by the FTE team: <https://www.fteqw.org/>
- **Quake** © id Software. The shareware data is downloaded from id's original release.
- The mods belong to their original authors: AirQuake, PainKeep, Headhunters, Team Fortress, ThreeWave /
  Thunderwalker CTF, Rocket Arena / Final Arena, Future vs Fantasy, Quake Rally, Get Rich Quake, Rune Quake.
- **7-Zip** by Igor Pavlov: <https://www.7-zip.org/>
- Based Quake Installer is made by **[USDQC](https://github.com/USDQC)**.

## License

Copyright (C) 2026 USDQC

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
option) any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
[LICENSE](LICENSE) file (GNU GPL v3) for details.

SPDX-License-Identifier: `GPL-3.0-or-later`

**Third-party components:**

- `tools/7za.exe` is the unmodified **7-Zip 9.20** command-line build by Igor Pavlov, licensed under the
  **GNU LGPL 2.1 or later** (see `tools/7za-license.txt`). It runs as a separate program and is used only to
  unpack the shareware archive on Windows; the Windows exe has it built in. Source code: <https://www.7-zip.org/> (`7z920.tar.bz2`, also at
  <https://sourceforge.net/projects/sevenzip/files/7-Zip/9.20/>).
- unezQuake, FTE, the Quake shareware data and the mods are **not** part of this repository or its packages.
  They are downloaded at install time and keep their own licences.
