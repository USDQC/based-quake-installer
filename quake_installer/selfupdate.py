"""Update Based Quake Installer itself from its GitHub releases.

Never touches game installs or configs: it only writes to a temp folder and to the
folder the installer program itself runs from.

  Windows exe (PyInstaller):  download BasedQuakeInstaller-windows-x64.zip, check it,
                              rename the running exe to .old, put the new exe in place,
                              restart. The .old file is deleted on the next start.
  Debian package (/opt):      download the .deb, install it with pkexec apt-get.
  Linux tarball / source:     download the matching archive and copy its files over the
                              program folder.
Anything else (read-only folder, git checkout, no matching asset): open the release page.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from . import __version__, download as dl
from .download import DownloadError

REPO = "USDQC/based-quake-installer"
API_URL = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_PAGE = "https://github.com/%s/releases/latest" % REPO
EXE_NAME = "BasedQuakeInstaller.exe"
DEB_DIR = "/opt/based-quake-installer"
DEB_LIST = "/var/lib/dpkg/info/based-quake-installer.list"

STATUS_UPDATE = "update"
STATUS_LATEST = "latest"
STATUS_ERROR = "error"

KIND_EXE = "exe"
KIND_DEB = "deb"
KIND_TARBALL = "tarball"
KIND_SOURCE_WIN = "source-windows"
KIND_GIT = "git"
KIND_UNSUPPORTED = "unsupported"

ASSET_PATTERNS = {
    KIND_EXE: r"^BasedQuakeInstaller-windows-x64\.zip$",
    KIND_DEB: r"^based-quake-installer_[0-9][^_]*_all\.deb$",
    KIND_TARBALL: r"^based-quake-installer-linux\.tar\.gz$",
    KIND_SOURCE_WIN: r"^based-quake-installer-source-windows\.zip$",
}


class SelfUpdateError(Exception):
    pass


# ------------------------------------------------------------------ versions
_VER_RE = re.compile(r"^\s*v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?\s*$")


def parse_version(text):
    """'v1.6.5' -> (1, 6, 5, ()); '1.7.0-rc.1' -> (1, 7, 0, ('rc', 1)). None if not a version."""
    m = _VER_RE.match(str(text or ""))
    if not m:
        return None
    pre = ()
    if m.group(4):
        pre = tuple(int(p) if p.isdigit() else p for p in m.group(4).split("."))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), pre)


def _key(v):
    major, minor, patch, pre = v
    # Semver: a pre-release sorts before the release; numeric ids before text ids.
    ids = tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in pre)
    return (major, minor, patch, 0 if pre else 1, ids)


def compare_versions(a, b):
    """-1, 0 or 1 like cmp(a, b). Raises ValueError for something that isn't a version."""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        raise ValueError("not a version: %r / %r" % (a, b))
    ka, kb = _key(pa), _key(pb)
    return (ka > kb) - (ka < kb)


def is_newer(remote, local):
    return compare_versions(remote, local) > 0


# ------------------------------------------------------------------ check
class Release(object):
    def __init__(self, data):
        self.tag = str(data.get("tag_name") or "")
        self.version = self.tag[1:] if self.tag[:1] in "vV" else self.tag
        self.name = data.get("name") or self.tag
        self.notes = short_notes(data.get("body") or "")
        self.html_url = data.get("html_url") or RELEASES_PAGE
        self.assets = [{"name": a.get("name") or "", "size": a.get("size"),
                        "url": a.get("browser_download_url") or "",
                        "digest": a.get("digest") or ""}
                       for a in (data.get("assets") or []) if isinstance(a, dict)]


class CheckResult(object):
    def __init__(self, status, release=None, message=""):
        self.status = status
        self.release = release
        self.message = message


def short_notes(body, max_lines=12, max_chars=700):
    """Release notes as plain text: no markdown marks, at most a dozen lines."""
    lines = []
    for line in body.replace("\r\n", "\n").split("\n"):
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)   # [text](url) -> text
        line = line.replace("**", "").replace("`", "").rstrip()
        line = re.sub(r"^#+\s*", "", line)
        if line.strip() or (lines and lines[-1]):
            lines.append(line)
    text = "\n".join(lines[:max_lines]).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + " …"
    return text


def _friendly(msg):
    if "HTTP 403" in msg or "HTTP 429" in msg:
        return "GitHub's limit for update checks was reached. Try again in an hour."
    if "HTTP 404" in msg:
        return "No release found on GitHub."
    return "Couldn't reach GitHub. Check your internet connection. (%s)" % msg.split("\n")[0]


def check(current=__version__, get_json=None, api_url=None, timeout=10):
    """Ask GitHub for the latest release. Never raises; errors become STATUS_ERROR."""
    get_json = get_json or dl.get_json
    url = api_url or os.environ.get("BQI_SELFUPDATE_API") or API_URL
    try:
        data = get_json(url, timeout=timeout)
    except DownloadError as exc:
        return CheckResult(STATUS_ERROR, message=_friendly(str(exc)))
    except Exception as exc:  # anything unexpected (bad JSON, ...)
        return CheckResult(STATUS_ERROR, message=_friendly(str(exc)))
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return CheckResult(STATUS_LATEST, message="You have the latest version (%s)." % current)
    rel = Release(data)
    if parse_version(rel.tag) is None:
        return CheckResult(STATUS_ERROR, rel, "The latest release has an odd tag: %r" % rel.tag)
    if is_newer(rel.tag, current):
        return CheckResult(STATUS_UPDATE, rel, "Version %s is available (you have %s)."
                           % (rel.version, current))
    return CheckResult(STATUS_LATEST, rel, "You have the latest version (%s)." % current)


# ------------------------------------------------------------------ install kind
def program_dir():
    """Folder of the running program: the exe's folder (frozen) or the source folder."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def install_kind(frozen=None, is_windows=None, base_dir=None, deb_list=DEB_LIST):
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    is_windows = (os.name == "nt") if is_windows is None else is_windows
    base = os.path.abspath(base_dir or program_dir())
    if frozen:
        return KIND_EXE if is_windows else KIND_UNSUPPORTED
    if os.path.isdir(os.path.join(base, ".git")):
        return KIND_GIT  # a developer checkout: use git, don't overwrite it
    if not is_windows and base.rstrip("/") == DEB_DIR and os.path.isfile(deb_list):
        return KIND_DEB
    return KIND_SOURCE_WIN if is_windows else KIND_TARBALL


def pick_asset(assets, kind):
    pat = ASSET_PATTERNS.get(kind)
    if not pat:
        return None
    for a in assets:
        if re.match(pat, a.get("name") or ""):
            return a
    return None


def folder_writable(path):
    try:
        fd, tmp = tempfile.mkstemp(prefix=".bqi-write-test-", dir=path)
        os.close(fd)
        os.remove(tmp)
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ download + verify
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path, asset):
    """Size, sha256 (GitHub's asset digest when given) and archive integrity."""
    size = asset.get("size")
    if size and os.path.getsize(path) != size:
        raise SelfUpdateError("Download is the wrong size (%d, expected %d)."
                              % (os.path.getsize(path), size))
    digest = (asset.get("digest") or "").lower()
    if digest.startswith("sha256:"):
        if sha256_of(path) != digest[7:]:
            raise SelfUpdateError("Download doesn't match its sha256 checksum.")
    name = asset.get("name") or path
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()
                if bad:
                    raise SelfUpdateError("Damaged file in the zip: %s" % bad)
        elif name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as t:
                for _m in t:
                    pass
        elif name.endswith(".deb"):
            with open(path, "rb") as fh:
                if fh.read(8) != b"!<arch>\n":
                    raise SelfUpdateError("The .deb file is damaged.")
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError) as exc:
        raise SelfUpdateError("The downloaded file is damaged (%s)." % exc)


def fetch(asset, dest_dir, progress=None, cancel_event=None, download=None):
    download = download or dl.download
    dest = os.path.join(dest_dir, os.path.basename(asset["name"]))
    download(asset["url"], dest, progress=progress, cancel_event=cancel_event)
    verify(dest, asset)
    return dest


# ------------------------------------------------------------------ apply
def apply_exe(zip_path, exe_path):
    """Swap in the new exe: running exe -> .old, new exe -> exe_path. Rolls back on error."""
    new = exe_path + ".new"
    old = exe_path + ".old"
    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.replace("\\", "/").split("/")[-1] == EXE_NAME]
        if not members:
            raise SelfUpdateError("%s is not in the download." % EXE_NAME)
        with z.open(sorted(members, key=len)[0]) as src, open(new, "wb") as dst:
            shutil.copyfileobj(src, dst)
    with open(new, "rb") as fh:
        magic = fh.read(2)
    if magic != b"MZ":  # closed first: Windows can't delete an open file
        os.remove(new)
        raise SelfUpdateError("The new exe is not a Windows program.")
    if os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    try:
        os.replace(exe_path, old)  # Windows lets a running exe be renamed, not deleted
    except OSError as exc:
        os.remove(new)
        raise SelfUpdateError("Can't replace %s (%s)." % (exe_path, exc))
    try:
        os.replace(new, exe_path)
    except OSError as exc:
        os.replace(old, exe_path)
        raise SelfUpdateError("Can't put the new exe in place (%s)." % exc)
    return exe_path


def cleanup_old(exe_path=None):
    """Delete the .old exe a previous self-update left behind. Quiet on failure."""
    if exe_path is None:
        if not getattr(sys, "frozen", False):
            return False
        exe_path = os.path.abspath(sys.executable)
    old = exe_path + ".old"
    if os.path.exists(old):
        try:
            os.remove(old)
            return True
        except OSError:
            return False
    return False


def _safe_members_tar(t):
    for m in t.getmembers():
        if m.isfile():
            yield m.name, m


def apply_files(archive_path, target_dir, strip_top=None):
    """Copy every file of the archive over target_dir (nothing is deleted).

    strip_top: leading folder in the archive to drop (the tarball has
    based-quake-installer/...). Refuses paths that would leave target_dir."""
    target = os.path.realpath(target_dir)
    written = []

    def dest_for(name):
        parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
        if strip_top and parts and parts[0] == strip_top:
            parts = parts[1:]
        if not parts or ".." in parts or ":" in parts[0]:
            return None
        if parts[0] in ("__pycache__",) or "__pycache__" in parts:
            return None
        d = os.path.realpath(os.path.join(target, *parts))
        if not d.startswith(target + os.sep):
            raise SelfUpdateError("Unsafe path in the download: %s" % name)
        return d

    def write(dest, src, mode=None):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".bqi-new"
        with open(tmp, "wb") as fh:
            shutil.copyfileobj(src, fh)
        if mode:
            os.chmod(tmp, mode)
        os.replace(tmp, dest)
        written.append(dest)

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                dest = dest_for(info.filename)
                if dest:
                    with z.open(info) as src:
                        write(dest, src)
    else:
        with tarfile.open(archive_path, "r:gz") as t:
            for name, m in _safe_members_tar(t):
                dest = dest_for(name)
                if dest:
                    write(dest, t.extractfile(m), m.mode & 0o777)
    return written


def deb_command(deb_path):
    return ["pkexec", "apt-get", "install", "-y", os.path.abspath(deb_path)]


def apply_deb(deb_path, run=None, which=shutil.which):
    run = run or subprocess.run
    if not which("pkexec"):
        raise SelfUpdateError("pkexec is not available.")
    proc = run(deb_command(deb_path), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode in (126, 127):
        raise SelfUpdateError("Install was cancelled or not authorised.")
    if proc.returncode != 0:
        out = (proc.stdout or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
        raise SelfUpdateError("apt-get failed (%d): %s" % (proc.returncode, " ".join(out)))


def restart_command(kind, base_dir=None):
    base = base_dir or program_dir()
    if kind == KIND_EXE:
        return [os.path.abspath(sys.executable)]
    if kind == KIND_DEB:
        return ["/usr/bin/based-quake-installer"]
    return [sys.executable, os.path.join(base, "installer_gui.py")]


def restart_env():
    """Environment for the restarted program (a fresh PyInstaller onefile start)."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


class Outcome(object):
    """What the GUI should do next: restart (restart_cmd) or open the page (url)."""

    def __init__(self, restart_cmd=None, url=None, message=""):
        self.restart_cmd = restart_cmd
        self.url = url
        self.message = message


def perform(release, kind=None, base_dir=None, exe_path=None, progress=None,
            cancel_event=None, log=None, download=None, run=None, which=shutil.which):
    """Download and apply an update. Returns an Outcome; only SelfUpdateError /
    DownloadError / Cancelled escape (the GUI shows them and offers the page)."""
    log = log or (lambda m: None)
    kind = kind or install_kind(base_dir=base_dir)
    base = os.path.abspath(base_dir or program_dir())
    page = release.html_url or RELEASES_PAGE
    if kind in (KIND_GIT, KIND_UNSUPPORTED):
        why = ("This copy is a git checkout; update it with git pull."
               if kind == KIND_GIT else "This copy can't update itself.")
        return Outcome(url=page, message=why + " Opening the release page.")
    asset = pick_asset(release.assets, kind)
    if not asset:
        return Outcome(url=page, message="The release has no download for this kind of "
                                         "install. Opening the release page.")
    target = os.path.dirname(exe_path or sys.executable) if kind == KIND_EXE else base
    if kind != KIND_DEB and not folder_writable(target):
        return Outcome(url=page, message="Can't write to %s. Download the new version from "
                                         "the release page instead." % target)
    tmp = tempfile.mkdtemp(prefix="bqi-selfupdate-")
    try:
        log("Downloading %s ..." % asset["name"])
        path = fetch(asset, tmp, progress=progress, cancel_event=cancel_event,
                     download=download)
        log("Checked %s (size%s)." % (asset["name"],
                                      ", sha256" if asset.get("digest") else ""))
        if kind == KIND_EXE:
            exe = exe_path or os.path.abspath(sys.executable)
            apply_exe(path, exe)
            log("Replaced %s" % exe)
            return Outcome(restart_cmd=[exe], message="Updated to %s." % release.version)
        if kind == KIND_DEB:
            try:
                apply_deb(path, run=run, which=which)
            except SelfUpdateError as exc:
                keep = os.path.join(tempfile.gettempdir(), os.path.basename(path))
                shutil.copyfile(path, keep)
                return Outcome(url=page, message="%s Install it yourself with:\n  sudo apt "
                                                 "install %s" % (exc, keep))
            log("Installed %s" % asset["name"])
            return Outcome(restart_cmd=restart_command(KIND_DEB),
                           message="Updated to %s." % release.version)
        top = "based-quake-installer" if kind == KIND_TARBALL else None
        files = apply_files(path, base, strip_top=top)
        log("Replaced %d program files in %s" % (len(files), base))
        return Outcome(restart_cmd=restart_command(kind, base),
                       message="Updated to %s." % release.version)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
