"""Folder rules that keep the unezQuake and FTE trees apart.

Everything that picks engine folders (Settings dialog, Install button, updater,
CLI) goes through check_engine_folders() / check_existing_folders(), so the two
clients can never end up sharing or nesting a folder.
"""

import ntpath
import os
import posixpath

from .constants import FTE_DIRNAME, UNEZ_DIRNAME

HOST_WINDOWS = os.name == "nt"
NAMES = {"unez": "unezQuake", "fte": "FTE"}


class FolderError(ValueError):
    """A folder choice that would mix up the engine folders."""


def clean(path):
    """Strip spaces/quotes and expand ~ (no other changes)."""
    p = str(path or "").strip().strip('"').strip()
    return os.path.expanduser(p) if p else ""


def is_full_path(path, windows=HOST_WINDOWS):
    """True for an absolute path. On Windows that means a drive path such as
    C:\\Games (not the drive-relative C:Games) or a UNC path such as
    \\\\server\\share or //server/share."""
    p = clean(path)
    if not p:
        return False
    if not windows:
        return posixpath.isabs(p)
    if not ntpath.isabs(p):
        return False
    drive, _rest = ntpath.splitdrive(p)
    if len(drive) == 2 and drive[1] == ":":
        return drive[0].isalpha()
    return drive[:2] in ("\\\\", "//") and len(drive) > 2


def norm(path, windows=HOST_WINDOWS):
    """Comparable form: normcase(realpath(...)). Windows-style paths checked on
    another OS (tests) use ntpath without resolving links."""
    p = clean(path)
    if not p:
        return ""
    if windows == HOST_WINDOWS:
        return os.path.normcase(os.path.realpath(p))
    mod = ntpath if windows else posixpath
    return mod.normcase(mod.normpath(mod.abspath(p) if not windows else p))


def is_inside(child, parent, windows=HOST_WINDOWS):
    """True when child is strictly inside parent (both already normalized)."""
    if not child or not parent or child == parent:
        return False
    sep = "\\" if windows else "/"
    base = parent if parent.endswith(sep) else parent + sep
    return child.startswith(base)


def same_folder(a, b, windows=HOST_WINDOWS):
    """True when two non-empty folder choices point at the same folder."""
    na, nb = norm(a, windows), norm(b, windows)
    return bool(na and nb and na == nb)


def _overlap(a, b, windows):
    return a == b or is_inside(a, b, windows) or is_inside(b, a, windows)


def check_existing_folders(unez, fte, windows=HOST_WINDOWS):
    """Mods only: the user's own client folders must be different and not nested."""
    u, f = norm(unez, windows), norm(fte, windows)
    if not u or not f:
        return
    if u == f:
        raise FolderError("unezQuake and FTE need their own separate folders. "
                          "Pick a different folder for one of them.")
    if is_inside(u, f, windows):
        raise FolderError("The unezQuake folder can't be inside the FTE folder. "
                          "Pick two separate folders.")
    if is_inside(f, u, windows):
        raise FolderError("The FTE folder can't be inside the unezQuake folder. "
                          "Pick two separate folders.")


def check_engine_folders(root, unez, fte, windows=HOST_WINDOWS, installed=None):
    """Full install: validate the folders the engines will really use.

    unez / fte are the effective folders (None for an engine that is turned off).
    installed maps a turned-off engine to the folder it still lives in (from the
    manifest), so a leftover install can't be nested inside the active one.
    Raises FolderError with a message meant for the user.
    """
    r = norm(root, windows)
    mod = ntpath if windows else posixpath
    dirs = {"unez": norm(unez, windows), "fte": norm(fte, windows)}
    defaults = {
        "unez": norm(mod.join(clean(root), UNEZ_DIRNAME), windows) if r else "",
        "fte": norm(mod.join(clean(root), FTE_DIRNAME), windows) if r else "",
    }
    installed = installed or {}
    check_existing_folders(unez, fte, windows)
    for kind, d in dirs.items():
        if not d:
            continue
        name = NAMES[kind]
        if r and d == r:
            raise FolderError(
                "The %s folder can't be the install folder itself. Leave it empty "
                "to use %s, or pick a folder of its own." % (name, defaults[kind]))
        if r and is_inside(r, d, windows):
            raise FolderError(
                "The %s folder can't contain the install folder. Pick a folder that "
                "isn't above %s." % (name, r))
        other = "fte" if kind == "unez" else "unez"
        # Don't collide with the other engine's default folder, or with a leftover
        # install when that engine is turned off.
        candidates = [defaults[other]]
        if not dirs[other]:
            candidates.append(norm(installed.get(other), windows))
        for od in candidates:
            if od and _overlap(d, od, windows):
                raise FolderError(
                    "The %s folder can't be in or around the %s folder (%s). Pick "
                    "a folder of its own." % (name, NAMES[other], od))
