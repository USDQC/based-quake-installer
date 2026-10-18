"""FTE engine-side defaults (default.fmf) and optional launch helpers.

NO batch files are written by the installer. FTE gets -nohome behavior via
default.fmf DISABLEHOMEDIR so double-clicking the exe in the FTE folder is enough
(working directory = basedir).

fte_args() remains for tests / advanced callers that still want explicit
-nohome -basedir on the command line.
"""

import os
import re

from .constants import FTE_REQUIRED_FLAGS


def _clean_dir(path):
    path = os.path.normpath(os.path.abspath(path))
    # Avoid a trailing backslash: "C:\Games\FTE\" would escape the closing quote.
    if len(path) > 3:
        path = path.rstrip("\\/")
    return path


def fte_args(fte_dir, game=None):
    """Argument list for FTE. Always includes -nohome and -basedir (+ -game for mods)."""
    args = ["-nohome", "-basedir", _clean_dir(fte_dir)]
    if game:
        args += ["-game", game]
    assert all(f in args for f in FTE_REQUIRED_FLAGS)
    return args


def fte_args_string(fte_dir, game=None):
    s = '-nohome -basedir "%s"' % _clean_dir(fte_dir)
    if game:
        s += " -game %s" % game
    assert all(f in s for f in FTE_REQUIRED_FLAGS)
    return s


def unez_args(game=None):
    """Argument list for UnezQuake (+ -game for mods)."""
    if game:
        return ["-game", game]
    return []


def unez_args_string(game=None):
    if game:
        return "-game %s" % game
    return ""


# Minimal AfterQuake-compatible manifest when AfterQuake did not ship one
# (e.g. engine-only fallback). disablehomedir replaces needing -nohome on the CLI.
_MINIMAL_FMF = """\
FTEManifestVer 1
game afterquake
name "AfterQuake"
protocolname "FTE-Quake DarkPlaces-Quake"
basegame id1
basegame qw
basegame *fte
disablehomedir 1
"""


def ensure_fte_default_fmf(fte_dir, log=print):
    """Ensure FTE\\default.fmf disables the homedir (engine-side -nohome).

    Prefer patching AfterQuake's existing manifest so package/update lines stay.
    Returns the path written or patched.
    """
    path = os.path.join(fte_dir, "default.fmf")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # Already disabled?
        if re.search(r"(?im)^\s*disablehomedir\s+(1|never)\b", text):
            log("  OK: default.fmf already has disablehomedir (no home dir)")
            return path
        # Replace an explicit enable, or append.
        new, n = re.subn(
            r"(?im)^\s*disablehomedir\s+\S+.*$",
            "disablehomedir 1",
            text,
            count=1,
        )
        if n:
            text = new
            action = "updated disablehomedir in"
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "disablehomedir 1\n"
            action = "appended disablehomedir to"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        log("  OK: %s %s" % (action, path))
        return path
    os.makedirs(fte_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_MINIMAL_FMF)
    log("  OK: wrote %s (disablehomedir 1)" % path)
    return path
