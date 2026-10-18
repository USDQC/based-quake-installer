"""URLs, checksums and defaults."""

APP_TITLE = "Based Quake Installer"
USER_AGENT = "Based-Quake-Installer/1.6 (+python-urllib)"

import os as _os
import sys as _sys

if _os.name == "nt":
    DEFAULT_ROOT = r"C:\Games"
else:
    DEFAULT_ROOT = _os.path.join(_os.path.expanduser("~"), "Games")
UNEZ_DIRNAME = "unezQuake"
FTE_DIRNAME = "FTE"

UNEZ_URL = "https://github.com/dusty-qw/unezquake/releases/download/2.1.1/unezQuake-windows-x64.zip"
UNEZ_RELEASES_API = "https://api.github.com/repos/dusty-qw/unezquake/releases/latest"
UNEZ_FALLBACK_TAG = "2.1.1"
# Official FTE downloads: https://www.fteqw.org/ links dated builds on fastdl.idtech.space
# (verified 2026-10-14). The old triptohell AfterQuake/engine zips (2022) are a fallback only.
FTEQW_ORG = "https://www.fteqw.org/"
FTE_OFFICIAL_BASE = "https://fastdl.idtech.space/bin/"
FTE_PINNED_DATE = "2026-07-13"
AFTERQUAKE_URL = "https://fte.triptohell.info/moodles/win64/afterquake.zip"   # fallback
FTE_ENGINE_URL = FTE_OFFICIAL_BASE + "fteqw-win-x86_64-%s.zip" % FTE_PINNED_DATE

SHAREWARE_URLS = (
    "https://ftp.gwdg.de/pub/misc/ftp.idsoftware.com/idstuff/quake/quake106.zip",
    "https://www.gamers.org/pub/idgames2/idstuff/quake/quake106.zip",
    "https://ftp.fu-berlin.de/pc/games/idgames2/idstuff/quake/quake106.zip",
)

PAK0_MD5 = "5906e5998fc3d896ddaf5e6a62e03abb"
PAK0_SIZE = 18689235

# Executable name candidates (first match wins).
UNEZ_EXE_CANDIDATES = ("unezquake.exe", "unezQuake.exe", "ezquake.exe")
FTE_EXE_CANDIDATES = (
    "fteqw64.exe",       # AfterQuake ships this
    "fteqw.exe",
    "fteglqw64.exe",
    "fteglqw.exe",
    "fteqw_win64.exe",
)
# Never pick these as the client (server, QC compiler, tools).
FTE_EXE_EXCLUDE = ("sv", "qcc", "qtv", "tool", "img", "iqm")

# Legacy: no launchers/shortcuts are written. FTE skips the home dir via default.fmf
# (DISABLEHOMEDIR); these flags are only what a manual command line would need.
FTE_REQUIRED_FLAGS = ("-nohome", "-basedir")

# Option values
MOVE_VANILLA = "vanilla"
MOVE_WASD = "wasd"
WEAP_VANILLA = "vanilla"
WEAP_MODERN = "modern"
LOOK_SOFT = "soft"
LOOK_GL = "gl"

MAX_NAME_LEN = 31  # QuakeWorld userinfo name limit

# ---------------------------------------------------------------- client platforms
PLATFORM_WINDOWS = "windows"
PLATFORM_LINUX = "linux"
PLATFORM_LABELS = {
    PLATFORM_WINDOWS: "Windows x64",
    PLATFORM_LINUX: "Linux x64",
}
FTE_BASE = "https://fte.triptohell.info/moodles/"   # legacy fallback mirror
# Per platform: unezQuake release-asset name, the fteqw.org asset key ("fteqw-<key>-DATE.zip"),
# and fallback FTE URLs (pinned official build, then triptohell AfterQuake / engine-only).
# Verified 2026-10-11. Releases are Windows + Linux only; the installer always uses
# the build for the OS it is running on.
PLATFORM_BUILDS = {
    PLATFORM_WINDOWS: {
        "unez_asset": "unezQuake-windows-x64.zip",
        "fte_key": "win-x86_64",
        "fte_urls": [FTE_OFFICIAL_BASE + "fteqw-win-x86_64-%s.zip" % FTE_PINNED_DATE,
                     FTE_BASE + "win64/afterquake.zip", FTE_BASE + "win64/fteqw_win64.zip"],
    },
    PLATFORM_LINUX: {
        "unez_asset": "unezQuake-linux-x86_64.zip",
        "fte_key": "linux-x86_64",
        "fte_urls": [FTE_OFFICIAL_BASE + "fteqw-linux-x86_64-%s.zip" % FTE_PINNED_DATE,
                     FTE_BASE + "linux_amd64/afterquake.zip",
                     FTE_BASE + "linux_amd64/fteqw_lin64.zip"],
    },
}


def host_platform():
    if _os.name == "nt":
        return PLATFORM_WINDOWS
    return PLATFORM_LINUX


UNEZ_EXE_BY_PLATFORM = {
    PLATFORM_WINDOWS: UNEZ_EXE_CANDIDATES,
    PLATFORM_LINUX: ("unezQuake-x86_64.AppImage", "unezquake", "unezQuake"),
}
FTE_EXE_BY_PLATFORM = {
    PLATFORM_WINDOWS: FTE_EXE_CANDIDATES,
    PLATFORM_LINUX: ("fteqw64", "fteqw", "fteqw-gl64"),
}
# Files an update must never overwrite once they exist (user configs).
PROTECTED_FILES = ("autoexec.cfg", "binds.cfg", "config.cfg", "default.fmf", "fte.cfg",
                   "sources.txt")  # sources.txt: unezQuake ezquake/sb, merged by sb_sources

# Mods download ONLY from the maintainer's Google Drive. This is the one stable
# "Anyone with the link" share link to mods.json (per-mod url/version/sha256/size).
# USDQC's mods.json link; Drive "Manage versions" keeps it stable.
MODS_INDEX_URL = "https://drive.google.com/file/d/1jReUW4XxYX7jWs3o5dWQaAoI5q2jdXnM/view"
