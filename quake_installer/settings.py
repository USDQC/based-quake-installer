"""Remember the last-used GUI settings (name, look, platform, root, binds, mod binds).

Stored per user, not in the install root, so a new install folder still starts
with your binds:
  Windows: %APPDATA%\\BasedQuakeInstaller\\settings.json
  Linux:   $XDG_CONFIG_HOME/based-quake-installer/settings.json (~/.config/...)
"""

import json
import os
import sys

FILENAME = "settings.json"
KEYS = ("root", "player_name", "look", "binds", "mod_binds", "check_installer_updates",
        "install_mode", "unez_path", "fte_path", "fte_cfg_choice", "theme",
        # CH - Settings window: which engines to install, per-engine target folders
        # and whether folder values are remembered at all.
        "remember_dirs", "install_unez", "install_fte",
        "unez_install_path", "fte_install_path",
        # Which mods are ticked on the main screen ({key: bool}).
        "mod_picks")


def settings_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "BasedQuakeInstaller")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "based-quake-installer")


def settings_path(folder=None):
    return os.path.join(folder or settings_dir(), FILENAME)


def load(folder=None):
    """Return the saved dict, or None on first run / unreadable file."""
    p = settings_path(folder)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out = {k: data[k] for k in KEYS if k in data}
    if not isinstance(out.get("binds", {}), dict):
        out.pop("binds", None)
    if not isinstance(out.get("mod_picks", {}), dict):
        out.pop("mod_picks", None)
    if not isinstance(out.get("mod_binds", {}), dict):
        out.pop("mod_binds", None)
    return out


def save(values, folder=None):
    d = folder or settings_dir()
    try:
        os.makedirs(d, exist_ok=True)
        p = settings_path(d)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({k: values.get(k) for k in KEYS if k in values}, fh, indent=2)
        os.replace(tmp, p)
        return p
    except OSError:
        return None  # settings are a convenience; never fail an install over them


def update(folder=None, **values):
    """Change a few saved values and keep the rest."""
    data = load(folder) or {}
    data.update(values)
    return save(data, folder)
