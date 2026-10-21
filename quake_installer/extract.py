"""Zip extraction (zip-slip safe), FTE/UnezQuake exe detection, pak0 extraction."""

import hashlib
import os
import shutil
import subprocess
import zipfile

from . import lha
from .constants import (
    FTE_EXE_CANDIDATES, FTE_EXE_EXCLUDE, UNEZ_EXE_CANDIDATES, PAK0_MD5, PAK0_SIZE,
)
from .paths import IS_WINDOWS, resource_path

CREATE_NO_WINDOW = 0x08000000


class ExtractError(Exception):
    pass


def safe_extract_zip(zip_path, dest_dir):
    """Extract a zip into dest_dir, refusing entries that escape it."""
    if not zipfile.is_zipfile(zip_path):
        raise ExtractError("Not a valid zip file (download corrupted?): %s" % zip_path)
    dest_real = os.path.realpath(dest_dir)
    os.makedirs(dest_real, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            target = os.path.realpath(os.path.join(dest_real, name))
            if target != dest_real and not target.startswith(dest_real + os.sep):
                raise ExtractError("Unsafe path in zip: %s" % info.filename)
        zf.extractall(dest_real)
        _apply_unix_modes(zf, dest_real)


def _apply_unix_modes(zf, dest_real):
    """Restore executable bits stored in the zip (Linux builds). No-op on Windows."""
    if IS_WINDOWS:
        return
    for info in zf.infolist():
        mode = (info.external_attr >> 16) & 0o777
        if mode & 0o111 and not info.is_dir():
            try:
                os.chmod(os.path.join(dest_real, info.filename), mode | 0o644)
            except OSError:
                pass


def mark_executable(path):
    """chmod +x when the host supports it (Linux). Returns True if applied."""
    if IS_WINDOWS or not os.path.isfile(path):
        return False
    try:
        os.chmod(path, os.stat(path).st_mode | 0o755)
        return True
    except OSError:
        return False


def flatten_root(stage_dir):
    """If the stage contains exactly one folder and nothing else, return that folder."""
    items = [i for i in os.listdir(stage_dir) if not i.startswith("__MACOSX")]
    if len(items) == 1 and os.path.isdir(os.path.join(stage_dir, items[0])):
        return os.path.join(stage_dir, items[0])
    return stage_dir


def normalize_dir_case(parent, name, log=None):
    """Linux: rename an existing case-variant of parent/name (e.g. PainKeep/) to
    the lowercase name the engines look up. Merges if both exist. Returns path."""
    want = os.path.join(parent, name)
    if os.name == "nt" or not os.path.isdir(parent) or os.path.isdir(want):
        return want
    for n in os.listdir(parent):
        p = os.path.join(parent, n)
        if n != name and n.lower() == name.lower() and os.path.isdir(p):
            os.rename(p, want)
            if log:
                log("  renamed %s -> %s (engines look up lowercase)" % (p, want))
            break
    return want


def copy_tree_over(src, dst, protect=(), skipped=None, ci=False):
    """Copy src/* into dst, overwriting files. Clear error if a file is locked.

    Files whose basename is in ``protect`` are not overwritten if they already exist
    (used by updates to keep the user's cfgs); their paths go into ``skipped``.
    """
    protect = {p.lower() for p in protect}
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tdir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(tdir, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(tdir, f)
            exists = os.path.exists(d)
            if ci and not exists and f.lower() in protect:
                exists = any(n.lower() == f.lower() for n in os.listdir(tdir))
            if f.lower() in protect and exists:
                if skipped is not None:
                    skipped.append(d)
                continue
            try:
                shutil.copy2(s, d)
            except PermissionError:
                raise ExtractError(
                    "Cannot overwrite %s (is the game running? close it and retry)" % d)


def find_file_ci(folder, names):
    """Case-insensitive lookup of the first of ``names`` directly inside folder."""
    try:
        listing = {n.lower(): n for n in os.listdir(folder)}
    except OSError:
        return None
    for n in names:
        hit = listing.get(n.lower())
        if hit and os.path.isfile(os.path.join(folder, hit)):
            return hit
    return None


def find_entry_ci(folder, names):
    """Like find_file_ci but also matches directories (app bundle folders)."""
    try:
        listing = {n.lower(): n for n in os.listdir(folder)}
    except OSError:
        return None
    for n in names:
        hit = listing.get(n.lower())
        if hit:
            return hit
    return None


def find_unez_exe_dir(stage, names=UNEZ_EXE_CANDIDATES):
    """Return (dir, exe_name) of the UnezQuake exe (or .app) anywhere in stage."""
    for root, dirs, _files in os.walk(stage):
        hit = find_entry_ci(root, names)
        if hit:
            return root, hit
        dirs[:] = [d for d in dirs if not d.lower().endswith(".app")]
    return None, None


def find_fte_exe(fte_dir, names=None):
    """Detect the real FTE client exe (AfterQuake: fteqw64.exe / Linux fteqw64)."""
    if names:
        hit = find_file_ci(fte_dir, names)
        if hit:
            return hit
    hit = find_file_ci(fte_dir, FTE_EXE_CANDIDATES)
    if hit:
        return hit
    try:
        names = sorted(os.listdir(fte_dir))
    except OSError:
        return None
    for n in names:
        low = n.lower()
        if low.startswith("fte") and low.endswith(".exe") and \
                not any(x in low for x in FTE_EXE_EXCLUDE):
            return n
    return None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pak0_is_valid(path):
    return (os.path.isfile(path) and os.path.getsize(path) == PAK0_SIZE
            and file_md5(path) == PAK0_MD5)


def extract_resource1(quake_zip, out_path):
    """Pull resource.1 out of quake106.zip."""
    if not zipfile.is_zipfile(quake_zip):
        raise ExtractError("quake106.zip is not a valid zip (bad mirror?)")
    with zipfile.ZipFile(quake_zip) as zf:
        member = None
        for n in zf.namelist():
            if n.replace("\\", "/").split("/")[-1].lower() == "resource.1":
                member = n
                break
        if not member:
            raise ExtractError("resource.1 not found inside quake106.zip")
        with zf.open(member) as src, open(out_path, "wb") as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    return out_path


def find_7za():
    """Bundled tools/7za.exe on Windows; 7z/7za on PATH elsewhere (dev/testing)."""
    bundled = resource_path("tools", "7za.exe")
    if IS_WINDOWS and os.path.isfile(bundled):
        return bundled
    if not IS_WINDOWS:
        # Full 7z first: Debian's reduced 7za lacks LZH support.
        for name in ("7z", "7za"):
            p = shutil.which(name)
            if p:
                return p
    return None


def run_7za(args, timeout=600):
    """Run 7za with args (list). Returns (exit_code, output)."""
    sevenzip = find_7za()
    if not sevenzip:
        raise ExtractError("7-Zip not available (Windows: tools\\7za.exe; Linux: install p7zip)")
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    proc = subprocess.run([sevenzip] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout, **kwargs)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def _run_7za(sevenzip, resource1, out_dir, pattern):
    extra = ["-r"] if "\\" not in pattern and "/" not in pattern else []
    return run_7za(["e", "-y", "-o" + out_dir, resource1, pattern] + extra)


def extract_pak0(resource1, work_dir, log=print):
    """Extract ID1/PAK0.PAK from resource.1 (LH5). Returns path to pak0.

    Uses bundled 7za.exe first; falls back to the built-in pure-Python LH5 decoder.
    """
    stage = os.path.join(work_dir, "pak-stage")
    os.makedirs(stage, exist_ok=True)
    sevenzip = find_7za()
    if sevenzip:
        log("  using 7za: %s" % sevenzip)
        for pattern in ("PAK0.PAK", "ID1\\PAK0.PAK", "ID1/PAK0.PAK"):
            try:
                code, out = _run_7za(sevenzip, resource1, stage, pattern)
            except (OSError, subprocess.SubprocessError, ExtractError) as exc:
                log("  7za could not run (%s)" % exc)
                break
            for root, _d, files in os.walk(stage):
                for f in files:
                    if f.lower() == "pak0.pak":
                        return os.path.join(root, f)
            if code != 0:
                log("  7za exit %d with pattern %s" % (code, pattern))
        log("  7za did not produce PAK0.PAK; using built-in LH5 decoder")
    else:
        log("  7za not found; using built-in LH5 decoder")
    out = os.path.join(stage, "pak0.pak")
    try:
        lha.extract_member(resource1, "ID1/PAK0.PAK", out)
    except lha.LhaError as exc:
        raise ExtractError("Could not extract PAK0.PAK from resource.1: %s" % exc)
    return out


def lowercase_tree(root, incoming_wins=True, log=None):
    """Rename files/dirs under root to lowercase. Linux engines (unezQuake) look up
    gamedir files such as pak0.pak and gfx/ in lowercase, but 90s DOS zips ship
    PAK0.PAK, GFX/. On a clash: incoming_wins=True keeps the renamed entry, False
    keeps the existing lowercase one. Directories are merged. No-op on Windows."""
    if os.name == "nt" or not os.path.isdir(root):
        return 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames + dirnames:
            low = name.lower()
            if low == name:
                continue
            src, dst = os.path.join(dirpath, name), os.path.join(dirpath, low)
            if os.path.isdir(src) and not os.path.islink(src):
                if os.path.isdir(dst):
                    for item in os.listdir(src):  # children already lowercased
                        s2, d2 = os.path.join(src, item), os.path.join(dst, item)
                        if os.path.lexists(d2):
                            if not incoming_wins:
                                continue
                            if os.path.isdir(d2) and not os.path.islink(d2):
                                copy_tree_over(s2, d2)
                                continue
                            os.remove(d2)
                        shutil.move(s2, d2)
                    shutil.rmtree(src, ignore_errors=True)
                else:
                    os.rename(src, dst)
            elif os.path.lexists(dst):
                if incoming_wins:
                    os.remove(dst)
                    os.rename(src, dst)
                else:
                    os.remove(src)
            else:
                os.rename(src, dst)
            count += 1
    if count and log:
        log("  (lowercased %d file/folder name(s) for Linux engines)" % count)
    return count
