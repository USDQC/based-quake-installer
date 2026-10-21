"""Mods-only installs into existing unezQuake / FTE folders.

Folder validation plus FTE home-directory detection. The FTE rules mirror
fteqw engine/common/fs.c:
  * FS_Manifest_ParseTokens: default.fmf ``disablehomedir`` / ``homedirmode``:
    "auto" -> home only when needed, empty/non-zero/"never" -> no home dir,
    "0"/"force"/"always" -> always use the home dir. No line = auto.
    ``game <name>`` sets the installation name (default "quake"), ``name`` the
    formal name.
  * FS_GetBestHomeDir (unix): $FTEHOME if set (always used); otherwise
    $XDG_DATA_HOME/<game>/ (default ~/.local/share/<game>/), or the legacy
    ~/.<game>/ when that exists and the XDG one does not.
    (win32): first existing of %LOCALAPPDATA%, Saved Games, Documents/My Games,
    each with /<name>/ or /<game>/ (formal name "Quake" -> "FTE QW").
    In auto mode the home dir is used only if it already exists or the base
    (install) dir is not writable.
  * COM_InitHomedir: the manifest mode overrides that, and -homedir/-usehome/
    -nohome on the command line override everything (we can't see those).
  * FS_AddGameDirectory: when the home dir is on, <home>/<gamedir> is searched
    after (i.e. before, priority-wise) <install>/<gamedir> and is the only
    writable one, so cfgs placed there win and config.cfg is saved there.
"""

import os
import re

from .constants import FTE_EXE_BY_PLATFORM, UNEZ_EXE_BY_PLATFORM
from . import extract

MODE_HOME = "home"
MODE_INSTALL = "install"
MODE_ASK = "ask"


def _listing(path):
    try:
        return {n.lower(): n for n in os.listdir(path)}
    except OSError:
        return {}


def check_unez_folder(path):
    """[] when path looks like a unezQuake/ezQuake folder, else warning strings."""
    if not path or not os.path.isdir(path):
        return ["folder does not exist: %s" % path]
    names = _listing(path)
    exes = {n.lower() for v in UNEZ_EXE_BY_PLATFORM.values() for n in v}
    has_exe = any(n in exes or "ezquake" in n for n in names
                  if os.path.isfile(os.path.join(path, names[n])))
    warn = []
    if not has_exe:
        warn.append("no unezQuake/ezQuake program found in %s" % path)
    if "id1" not in names and "qw" not in names:
        warn.append("no id1/ or qw/ folder in %s" % path)
    return warn


def check_fte_folder(path):
    if not path or not os.path.isdir(path):
        return ["folder does not exist: %s" % path]
    names = _listing(path)
    has_exe = bool(extract.find_fte_exe(path, [n for v in FTE_EXE_BY_PLATFORM.values()
                                              for n in v]))
    has_exe = has_exe or any(n.startswith("fte") and os.path.isfile(os.path.join(path, o))
                             for n, o in names.items())
    warn = []
    if not has_exe:
        warn.append("no FTE program (fteqw*) found in %s" % path)
    if "id1" not in names and "qw" not in names:
        warn.append("no id1/ or qw/ folder in %s" % path)
    return warn


def parse_fmf(fte_dir):
    """{'game','name','homedir'} from <fte_dir>/default.fmf (any case); None if absent.
    homedir: 'auto' | 'never' | 'always'."""
    names = _listing(fte_dir)
    if "default.fmf" not in names:
        return None
    out = {"game": None, "name": None, "homedir": "auto"}
    try:
        with open(os.path.join(fte_dir, names["default.fmf"]), "r", encoding="utf-8",
                  errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.split("//", 1)[0].strip()
        m = re.match(r'(\S+)\s*(?:"([^"]*)"|(\S*))', line)
        if not m:
            continue
        cmd, arg = m.group(1).lower(), (m.group(2) if m.group(2) is not None else m.group(3))
        if cmd == "game":
            out["game"] = arg
        elif cmd == "name":
            out["name"] = arg
        elif cmd in ("disablehomedir", "homedirmode"):
            a = arg.lower()
            if a == "auto":
                out["homedir"] = "auto"
            elif not a or a == "never" or _atoi(a):
                out["homedir"] = "never"
            else:
                out["homedir"] = "always"
    return out


def _atoi(s):
    m = re.match(r"[+-]?\d+", s)
    return int(m.group(0)) if m else 0


def home_candidates(fmf, env=None, platform=None):
    """Ordered [(path, exists)] FTE would consider; first entry is the default."""
    env = os.environ if env is None else env
    platform = platform or ("windows" if os.name == "nt" else "linux")
    game = (fmf or {}).get("game") or "quake"
    out = []
    if platform == "windows":
        name = (fmf or {}).get("name")
        bases = [env.get("LOCALAPPDATA")]
        prof = env.get("USERPROFILE")
        if prof:
            bases += [os.path.join(prof, "Saved Games"),
                      os.path.join(prof, "Documents", "My Games")]
        subs = []
        if not name or name == "Quake":
            subs.append("FTE QW")
        elif not re.search(r'[(\[."|<>\\/:*?]', name):
            subs.append(name)
        if name and name != "Quake":
            subs.append(game)
        for b in bases:
            if b:
                for s in subs:
                    p = os.path.join(b, s)
                    out.append((p, os.path.isdir(p)))
        return out
    if env.get("FTEHOME"):
        return [(env["FTEHOME"], True)]  # FTEHOME: always used
    home = env.get("HOME") or os.path.expanduser("~")
    xdg = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    new, old = os.path.join(xdg, game), os.path.join(home, "." + game)
    if not os.path.isdir(new) and os.path.isdir(old):
        return [(old, True), (new, False)]
    return [(new, os.path.isdir(new)), (old, os.path.isdir(old))]


class FteConfig(object):
    def __init__(self, mode, install, home, reason, candidates=()):
        self.mode = mode          # MODE_HOME / MODE_INSTALL / MODE_ASK
        self.install = install
        self.home = home          # home dir FTE would use (None if unknown)
        self.reason = reason
        self.candidates = list(candidates)

    @property
    def write_root(self):
        """Where FTE reads/writes per-gamedir cfgs (None while MODE_ASK)."""
        if self.mode == MODE_HOME:
            return self.home
        if self.mode == MODE_INSTALL:
            return self.install
        return None

    def describe(self):
        if self.mode == MODE_ASK:
            return "FTE configs: unclear (%s)" % self.reason
        return "FTE configs: %s  (%s)" % (self.write_root, self.reason)


def detect_fte_config(fte_dir, env=None, platform=None, writable=None):
    """Work out FTE's effective write dir for an existing install (see module doc)."""
    env = os.environ if env is None else env
    fmf = parse_fmf(fte_dir)
    mode = (fmf or {}).get("homedir", "auto")
    cands = home_candidates(fmf, env, platform)
    existing = [p for p, ok in cands if ok]
    home = existing[0] if existing else (cands[0][0] if cands else None)
    if mode == "never":
        return FteConfig(MODE_INSTALL, fte_dir, home, "default.fmf disables the home dir")
    if mode == "always":
        return FteConfig(MODE_HOME, fte_dir, home, "default.fmf forces the home dir", cands)
    if (platform or ("windows" if os.name == "nt" else "linux")) != "windows" and \
            env.get("FTEHOME"):
        return FteConfig(MODE_HOME, fte_dir, home, "FTEHOME is set", cands)
    if writable is None:
        writable = os.access(fte_dir, os.W_OK)
    if not writable:
        return FteConfig(MODE_HOME, fte_dir, home, "install folder is read-only", cands)
    if existing:
        if fmf is None or not fmf.get("game"):
            # no manifest naming the game: FTE's built-in game name may differ
            return FteConfig(MODE_ASK, fte_dir, home,
                             "found home folder %s but no default.fmf names the game"
                             % existing[0], cands)
        return FteConfig(MODE_HOME, fte_dir, home, "home folder exists", cands)
    return FteConfig(MODE_INSTALL, fte_dir, home,
                     "no home folder yet and install folder is writable", cands)
