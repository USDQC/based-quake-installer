"""Folder rules for the unezQuake and FTE client folders.

Everything that picks engine folders (Settings, Install, mods-only and the
updater) goes through check_engine_folders() / check_existing_folders(). A
shared folder is allowed (the GUI warns first); nesting is not.
"""

import ntpath
import os
import posixpath

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


def same_folder_warning(path):
    """Message shown before letting both engines share one folder."""
    return ("unezQuake and FTE will share %s. Their configs and mod files "
            "will mix; the unezQuake config is written last." % path)


def check_existing_folders(unez, fte, windows=HOST_WINDOWS):
    """Clients may share one folder (the caller warns); they must not nest."""
    u, f = norm(unez, windows), norm(fte, windows)
    if not u or not f:
        return
    if is_inside(u, f, windows):
        raise FolderError("The unezQuake folder can't be inside the FTE folder. "
                          "Pick two separate folders or one shared folder.")
    if is_inside(f, u, windows):
        raise FolderError("The FTE folder can't be inside the unezQuake folder. "
                          "Pick two separate folders or one shared folder.")


def check_engine_folders(root, unez, fte, windows=HOST_WINDOWS, installed=None):
    """Full install: validate the folders the engines will really use.

    unez / fte are the effective folders (None for an engine that is turned off).
    installed maps a turned-off engine to the folder it still lives in (from the
    manifest), so a leftover install can't be nested inside the active one.
    Raises FolderError with a message meant for the user.
    """
    r = norm(root, windows)
    dirs = {"unez": norm(unez, windows), "fte": norm(fte, windows)}
    installed = installed or {}
    check_existing_folders(unez, fte, windows)
    for kind, d in dirs.items():
        if not d:
            continue
        name = NAMES[kind]
        if r and is_inside(r, d, windows):
            raise FolderError(
                "The %s folder can't contain the install folder. Pick a folder that "
                "isn't above %s." % (name, r))
        other = "fte" if kind == "unez" else "unez"
        if dirs[other]:
            continue  # both active: check_existing_folders already rejected nesting
        od = norm(installed.get(other), windows)
        if od and is_inside(d, od, windows):
            raise FolderError(
                "The %s folder can't be inside the %s folder (%s). Pick a folder "
                "of its own." % (name, NAMES[other], od))
        if od and is_inside(od, d, windows):
            raise FolderError(
                "The %s folder can't contain the %s folder (%s). Pick a folder "
                "of its own." % (name, NAMES[other], od))
