"""Installer self-update: version compare, GitHub API handling, assets, swap logic."""

import io
import os
import shutil
import stat
import tarfile
import tempfile
import unittest
import zipfile

from quake_installer import selfupdate as su, settings
from quake_installer.download import DownloadError

V166_ASSETS = [
    {"name": "based-quake-installer-linux.tar.gz", "size": 69952},
    {"name": "Based-Quake-Installer-Manual.pdf", "size": 518342},
    {"name": "based-quake-installer-source-windows.zip", "size": 392220},
    {"name": "based-quake-installer_1.6.6_all.deb", "size": 61160},
    {"name": "BasedQuakeInstaller-windows-x64.zip", "size": 11962463},
]


def api(tag="v1.7.0", **kw):
    d = {"tag_name": tag, "name": "Based Quake Installer", "draft": False, "prerelease": False,
         "html_url": "https://github.com/USDQC/based-quake-installer/releases/tag/" + tag,
         "body": "- **New** thing\n- `fix` [link](https://x)\n", "assets": [
             dict(a, browser_download_url="https://example.invalid/" + a["name"])
             for a in V166_ASSETS]}
    d.update(kw)
    return d


class VersionTests(unittest.TestCase):
    def test_compare(self):
        c = su.compare_versions
        self.assertEqual(c("v1.6.10", "1.6.9"), 1)
        self.assertEqual(c("1.6.6", "v1.6.6"), 0)
        self.assertEqual(c("1.6", "1.6.0"), 0)
        self.assertEqual(c("1.7.0-rc.1", "1.7.0"), -1)
        self.assertEqual(c("1.7.0-rc.2", "1.7.0-rc.1"), 1)
        self.assertEqual(c("1.7.0-rc.10", "1.7.0-rc.9"), 1)
        self.assertEqual(c("1.7.0-1", "1.7.0-alpha"), -1)  # numeric ids sort first
        self.assertEqual(c("2.0.0", "1.99.99"), 1)
        self.assertEqual(c("1.0.0+build5", "1.0.0"), 0)
        self.assertTrue(su.is_newer("v1.6.7", "1.6.6"))
        self.assertFalse(su.is_newer("v1.6.5", "1.6.6"))
        with self.assertRaises(ValueError):
            c("latest", "1.6.6")


class CheckTests(unittest.TestCase):
    def check(self, data=None, exc=None, current="1.6.6"):
        def get_json(url, timeout=None):
            if exc:
                raise exc
            return data
        return su.check(current=current, get_json=get_json)

    def test_newer(self):
        r = self.check(api("v1.7.0"))
        self.assertEqual(r.status, su.STATUS_UPDATE)
        self.assertEqual(r.release.version, "1.7.0")
        self.assertIn("1.7.0", r.message)
        self.assertEqual(r.release.notes, "- New thing\n- fix link")

    def test_same_or_older(self):
        self.assertEqual(self.check(api("v1.6.6")).status, su.STATUS_LATEST)
        self.assertEqual(self.check(api("v1.6.5")).status, su.STATUS_LATEST)
        self.assertIn("latest version", self.check(api("v1.6.6")).message)

    def test_draft_and_prerelease_ignored(self):
        self.assertEqual(self.check(api("v9.0.0", draft=True)).status, su.STATUS_LATEST)
        self.assertEqual(self.check(api("v9.0.0", prerelease=True)).status, su.STATUS_LATEST)

    def test_offline_and_rate_limit(self):
        r = self.check(exc=DownloadError("GET x failed: Cannot resolve host (no internet)"))
        self.assertEqual(r.status, su.STATUS_ERROR)
        self.assertIn("internet", r.message)
        r = self.check(exc=DownloadError("GET x failed: HTTP 403 rate limit exceeded"))
        self.assertEqual(r.status, su.STATUS_ERROR)
        self.assertIn("limit", r.message)
        self.assertEqual(self.check(exc=ValueError("bad json")).status, su.STATUS_ERROR)

    def test_bad_tag(self):
        self.assertEqual(self.check(api("nightly")).status, su.STATUS_ERROR)

    def test_env_override_url(self):
        seen = []
        os.environ["BQI_SELFUPDATE_API"] = "http://127.0.0.1:1/latest.json"
        try:
            su.check(get_json=lambda url, timeout=None: seen.append(url) or api())
        finally:
            del os.environ["BQI_SELFUPDATE_API"]
        self.assertEqual(seen, ["http://127.0.0.1:1/latest.json"])
        self.assertEqual(su.API_URL,
                         "https://api.github.com/repos/USDQC/based-quake-installer/releases/latest")


class AssetAndKindTests(unittest.TestCase):
    def test_pick_asset(self):
        p = lambda k: (su.pick_asset(V166_ASSETS, k) or {}).get("name")
        self.assertEqual(p(su.KIND_EXE), "BasedQuakeInstaller-windows-x64.zip")
        self.assertEqual(p(su.KIND_DEB), "based-quake-installer_1.6.6_all.deb")
        self.assertEqual(p(su.KIND_TARBALL), "based-quake-installer-linux.tar.gz")
        self.assertEqual(p(su.KIND_SOURCE_WIN), "based-quake-installer-source-windows.zip")
        self.assertIsNone(p(su.KIND_GIT))
        self.assertIsNone(su.pick_asset([], su.KIND_EXE))

    def test_install_kind(self):
        t = tempfile.mkdtemp()
        try:
            k = su.install_kind
            self.assertEqual(k(frozen=True, is_windows=True, base_dir=t), su.KIND_EXE)
            self.assertEqual(k(frozen=True, is_windows=False, base_dir=t), su.KIND_UNSUPPORTED)
            self.assertEqual(k(frozen=False, is_windows=False, base_dir=t), su.KIND_TARBALL)
            self.assertEqual(k(frozen=False, is_windows=True, base_dir=t), su.KIND_SOURCE_WIN)
            lst = os.path.join(t, "pkg.list")
            open(lst, "w").close()
            if os.name != "nt":  # /opt path; the .deb kind only exists on Linux
                self.assertEqual(k(frozen=False, is_windows=False, base_dir=su.DEB_DIR,
                                   deb_list=lst), su.KIND_DEB)
                self.assertEqual(k(frozen=False, is_windows=False, base_dir=su.DEB_DIR,
                                   deb_list=lst + ".missing"), su.KIND_TARBALL)
            os.mkdir(os.path.join(t, ".git"))
            self.assertEqual(k(frozen=False, is_windows=False, base_dir=t), su.KIND_GIT)
        finally:
            shutil.rmtree(t)


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


def make_tar(path, files):
    with tarfile.open(path, "w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            t.addfile(info, io.BytesIO(data))


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()

    def tearDown(self):
        for root, dirs, _files in os.walk(self.t):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
        shutil.rmtree(self.t, ignore_errors=True)

    def p(self, *parts):
        return os.path.join(self.t, *parts)

    def test_verify(self):
        z = self.p("a.zip")
        make_zip(z, {"x.txt": b"hello"})
        good = {"name": "a.zip", "size": os.path.getsize(z),
                "digest": "sha256:" + su.sha256_of(z)}
        su.verify(z, good)
        with self.assertRaises(su.SelfUpdateError):
            su.verify(z, dict(good, size=1))
        with self.assertRaises(su.SelfUpdateError):
            su.verify(z, dict(good, digest="sha256:" + "0" * 64))
        raw = open(z, "rb").read()
        with open(z, "r+b") as fh:  # corrupt the stored file data (CRC check fails)
            fh.seek(raw.index(b"hello"))
            fh.write(b"HELLO")
        with self.assertRaises(su.SelfUpdateError):
            su.verify(z, {"name": "a.zip"})
        d = self.p("x.deb")
        open(d, "wb").write(b"notadeb!")
        with self.assertRaises(su.SelfUpdateError):
            su.verify(d, {"name": "x.deb"})

    def test_exe_swap_and_cleanup(self):
        exe = self.p("BasedQuakeInstaller.exe")
        open(exe, "wb").write(b"MZ old")
        z = self.p("new.zip")
        make_zip(z, {"BasedQuakeInstaller.exe": b"MZ new", "README.md": b"r"})
        su.apply_exe(z, exe)
        self.assertEqual(open(exe, "rb").read(), b"MZ new")
        self.assertEqual(open(exe + ".old", "rb").read(), b"MZ old")
        self.assertFalse(os.path.exists(exe + ".new"))
        self.assertTrue(su.cleanup_old(exe))
        self.assertFalse(os.path.exists(exe + ".old"))
        self.assertFalse(su.cleanup_old(exe))

    def test_exe_swap_refuses_bad_zip(self):
        exe = self.p("BasedQuakeInstaller.exe")
        open(exe, "wb").write(b"MZ old")
        z = self.p("bad.zip")
        make_zip(z, {"other.exe": b"MZ"})
        with self.assertRaises(su.SelfUpdateError):
            su.apply_exe(z, exe)
        make_zip(z, {"BasedQuakeInstaller.exe": b"#!/bin/sh"})
        with self.assertRaises(su.SelfUpdateError):
            su.apply_exe(z, exe)
        self.assertEqual(open(exe, "rb").read(), b"MZ old")
        self.assertEqual(sorted(os.listdir(self.t)), ["BasedQuakeInstaller.exe", "bad.zip"])

    def test_apply_files_tarball(self):
        prog = self.p("prog")
        os.makedirs(os.path.join(prog, "quake_installer"))
        open(os.path.join(prog, "installer_gui.py"), "w").write("old")
        open(os.path.join(prog, "keep.txt"), "w").write("mine")
        tgz = self.p("t.tar.gz")
        make_tar(tgz, {"based-quake-installer/installer_gui.py": b"new",
                       "based-quake-installer/quake_installer/__init__.py": b"v",
                       "based-quake-installer/quake_installer/__pycache__/x.pyc": b"c"})
        written = su.apply_files(tgz, prog, strip_top="based-quake-installer")
        self.assertEqual(len(written), 2)
        self.assertEqual(open(os.path.join(prog, "installer_gui.py")).read(), "new")
        self.assertEqual(open(os.path.join(prog, "keep.txt")).read(), "mine")
        self.assertFalse(os.path.exists(os.path.join(prog, "quake_installer", "__pycache__")))

    def test_apply_files_refuses_escape(self):
        prog = self.p("prog")
        os.makedirs(prog)
        z = self.p("evil.zip")
        make_zip(z, {"../outside.txt": b"x"})
        su.apply_files(z, prog)  # ".." parts are skipped
        self.assertFalse(os.path.exists(self.p("outside.txt")))

    def fake_download(self, src):
        def download(url, dest, progress=None, cancel_event=None):
            shutil.copyfile(src, dest)
            if progress:
                progress(1, 1)
            return dest
        return download

    def release(self, assets):
        return su.Release(api("v9.9.9", assets=assets))

    def test_perform_tarball_end_to_end(self):
        prog = self.p("prog")
        games = self.p("Games", "unezQuake", "id1")
        os.makedirs(prog)
        os.makedirs(games)
        open(os.path.join(games, "based.cfg"), "w").write("name me")
        before = os.stat(os.path.join(games, "based.cfg")).st_mtime_ns
        tgz = self.p("based-quake-installer-linux.tar.gz")
        make_tar(tgz, {"based-quake-installer/installer_gui.py": b"print('9.9.9')"})
        asset = {"name": os.path.basename(tgz), "size": os.path.getsize(tgz),
                 "browser_download_url": "http://x/t.tar.gz",
                 "digest": "sha256:" + su.sha256_of(tgz)}
        out = su.perform(self.release([asset]), kind=su.KIND_TARBALL, base_dir=prog,
                         download=self.fake_download(tgz))
        self.assertEqual(open(os.path.join(prog, "installer_gui.py")).read(), "print('9.9.9')")
        self.assertEqual(out.restart_cmd[-1], os.path.join(prog, "installer_gui.py"))
        self.assertIsNone(out.url)
        self.assertEqual(os.stat(os.path.join(games, "based.cfg")).st_mtime_ns, before)

    def test_perform_exe(self):
        exe = self.p("BasedQuakeInstaller.exe")
        open(exe, "wb").write(b"MZ old")
        z = self.p("BasedQuakeInstaller-windows-x64.zip")
        make_zip(z, {"BasedQuakeInstaller.exe": b"MZ 9.9.9"})
        asset = {"name": os.path.basename(z), "size": os.path.getsize(z),
                 "browser_download_url": "http://x/z.zip"}
        out = su.perform(self.release([asset]), kind=su.KIND_EXE, exe_path=exe,
                         download=self.fake_download(z))
        self.assertEqual(out.restart_cmd, [exe])
        self.assertEqual(open(exe, "rb").read(), b"MZ 9.9.9")

    def test_perform_falls_back_to_release_page(self):
        prog = self.p("ro")
        os.makedirs(prog)
        os.chmod(prog, stat.S_IRUSR | stat.S_IXUSR)
        tgz = self.p("based-quake-installer-linux.tar.gz")
        make_tar(tgz, {"based-quake-installer/a": b"a"})
        asset = {"name": os.path.basename(tgz), "browser_download_url": "http://x"}
        rel = self.release([asset])
        if os.access(prog, os.W_OK):  # running as root: permissions don't apply
            self.skipTest("root can write anywhere")
        out = su.perform(rel, kind=su.KIND_TARBALL, base_dir=prog,
                         download=self.fake_download(tgz))
        self.assertIsNone(out.restart_cmd)
        self.assertEqual(out.url, rel.html_url)
        self.assertIn("Can't write", out.message)
        out = su.perform(rel, kind=su.KIND_GIT, base_dir=prog)
        self.assertIn("git", out.message)
        out = su.perform(self.release([]), kind=su.KIND_EXE, exe_path=self.p("x.exe"))
        self.assertIn("no download", out.message)

    def test_deb(self):
        deb = self.p("based-quake-installer_9.9.9_all.deb")
        open(deb, "wb").write(b"!<arch>\nrest")
        asset = {"name": os.path.basename(deb), "browser_download_url": "http://x"}
        calls = []

        class P(object):
            def __init__(self, rc):
                self.returncode, self.stdout = rc, b"E: failed"

        def run_ok(cmd, **kw):
            calls.append(cmd)
            return P(0)
        out = su.perform(self.release([asset]), kind=su.KIND_DEB, download=self.fake_download(deb),
                         run=run_ok, which=lambda n: "/usr/bin/" + n)
        self.assertEqual(calls[0][:4], ["pkexec", "apt-get", "install", "-y"])
        self.assertTrue(calls[0][4].endswith(".deb"))
        self.assertEqual(out.restart_cmd, ["/usr/bin/based-quake-installer"])
        out = su.perform(self.release([asset]), kind=su.KIND_DEB, download=self.fake_download(deb),
                         run=lambda cmd, **kw: P(126), which=lambda n: "/usr/bin/" + n)
        self.assertIsNone(out.restart_cmd)
        self.assertIn("sudo apt install", out.message)
        out = su.perform(self.release([asset]), kind=su.KIND_DEB, download=self.fake_download(deb),
                         which=lambda n: None)
        self.assertIn("pkexec is not available", out.message)


class SettingTests(unittest.TestCase):
    def test_update_keeps_other_values(self):
        t = tempfile.mkdtemp()
        try:
            settings.save({"player_name": "Ranger", "binds": {"jump": "SPACE"}}, t)
            settings.update(t, check_installer_updates=False)
            d = settings.load(t)
            self.assertEqual(d["player_name"], "Ranger")
            self.assertEqual(d["binds"], {"jump": "SPACE"})
            self.assertIs(d["check_installer_updates"], False)
        finally:
            shutil.rmtree(t)

    def test_restart_env_resets_pyinstaller(self):
        self.assertEqual(su.restart_env()["PYINSTALLER_RESET_ENVIRONMENT"], "1")


if __name__ == "__main__":
    unittest.main()
