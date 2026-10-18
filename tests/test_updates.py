import os
import shutil
import tempfile
import unittest
import zipfile

from quake_installer import clients, manifest, updater
from quake_installer.download import DownloadError


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_roundtrip_and_bad_json(self):
        m = manifest.empty("linux")
        manifest.record(m, "client:unez", {"version": "2.1", "url": "u", "size": 5},
                        files=["a"], platform="linux")
        manifest.save(self.tmp, m)
        back = manifest.load(self.tmp)
        self.assertEqual(back["components"]["client:unez"]["version"], "2.1")
        self.assertEqual(back["components"]["client:unez"]["platform"], "linux")
        with open(manifest.path_for(self.tmp), "w") as fh:
            fh.write("{broken")
        self.assertEqual(manifest.load(self.tmp)["components"], {})

    def test_compare_rules(self):
        c = manifest.compare
        self.assertEqual(c(None, {"version": "2.1"}), manifest.STATUS_MISSING)
        self.assertEqual(c({"version": "2.1"}, None), manifest.STATUS_UNAVAILABLE)
        self.assertEqual(c({"version": "2.1"}, {"error": "offline"}), manifest.STATUS_ERROR)
        self.assertEqual(c({"version": "2.0.3"}, {"version": "2.1"}), manifest.STATUS_OUTDATED)
        self.assertEqual(c({"version": "2.1"}, {"version": "2.1"}), manifest.STATUS_OK)
        self.assertEqual(c({"etag": 'W/"a"'}, {"etag": '"a"'}), manifest.STATUS_OK)
        self.assertEqual(c({"etag": '"a"'}, {"etag": '"b"'}), manifest.STATUS_OUTDATED)
        self.assertEqual(c({"size": 1, "last_modified": "x"}, {"size": 1, "last_modified": "x"}),
                         manifest.STATUS_OK)
        self.assertEqual(c({"size": 1}, {"size": 2}), manifest.STATUS_OUTDATED)
        self.assertEqual(c({}, {}), manifest.STATUS_OK)  # nothing comparable: no fake update
        self.assertEqual(c({"version": "2.1", "platform": "windows"}, {"version": "2.1"},
                           "linux"), manifest.STATUS_OUTDATED)

    def test_compare_mod_steps(self):
        inst = {"steps": [{"file": "a.zip", "size": 10, "etag": '"1"'}]}
        same = {"steps": [{"file": "A.ZIP", "size": 10, "etag": '"1"'}]}
        new = {"steps": [{"file": "a.zip", "size": 11, "etag": '"2"'}]}
        self.assertEqual(manifest.compare(inst, same), manifest.STATUS_OK)
        self.assertEqual(manifest.compare(inst, new), manifest.STATUS_OUTDATED)
        # pre-1.6 install (no record): spec size vs remote size
        self.assertEqual(manifest.compare({"steps": []}, {"steps": [
            {"file": "b.zip", "size": 5, "spec_size": 5}]}), manifest.STATUS_OK)
        self.assertEqual(manifest.compare({"steps": []}, {"steps": [
            {"file": "b.zip", "size": 6, "spec_size": 5}]}), manifest.STATUS_OUTDATED)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _head(self, url):
        if "dead" in url:
            raise DownloadError("offline")
        return {"url": url, "size": 100, "etag": '"e"', "last_modified": "d"}

    def test_check_with_mocks(self):
        m = manifest.empty("windows")
        manifest.record(m, "client:unez", {"version": "2.0.3"}, platform="windows")
        manifest.record(m, "client:fte", {"etag": '"e"', "size": 100}, platform="windows")
        manifest.record(m, "mod:x", {"file": "x.zip", "size": 100, "version": "1",
                                     "sha256": "aa" * 32})
        manifest.record(m, "mod:z", {"file": "z.zip", "size": 100, "version": "1",
                                     "sha256": "aa" * 32})
        manifest.record(m, "mod:old", {"steps": [{"file": "o.zip", "size": 1}]})
        manifest.save(self.tmp, m)
        specs = [
            {"key": "x", "title": "X", "gamedir": "x", "clients": ["fte"], "version": "1",
             "url": "https://drive.google.com/file/d/xxxxxxxxxxxx/view", "sha256": "AA" * 32},
            {"key": "z", "title": "Z", "gamedir": "z", "clients": ["fte"], "version": "1",
             "url": "https://drive.google.com/file/d/zzzzzzzzzzzz/view", "sha256": "bb" * 32},
            {"key": "old", "title": "Old", "gamedir": "old", "clients": ["fte"], "version": "1",
             "url": "https://drive.google.com/file/d/oooooooooooo/view", "sha256": "cc" * 32},
            {"key": "y", "title": "Y", "gamedir": "y", "clients": ["fte"],
             "url": "PASTE_DRIVE_LINK", "sha256": "dd" * 32},
            {"key": "r", "title": "R", "gamedir": "r", "binds_only": True},
        ]
        items = updater.check_updates(
            self.tmp, "windows", specs=specs, log=lambda *a: None, head=self._head,
            resolve_unez=lambda p: {"version": "2.1", "url": "u"},
            resolve_fte=lambda p: {"etag": '"e"', "size": 100, "url": "f"})
        st = {i.component: i.status for i in items}
        self.assertEqual(st["client:unez"], manifest.STATUS_OUTDATED)
        self.assertEqual(st["client:fte"], manifest.STATUS_OK)
        self.assertEqual(st["mod:x"], manifest.STATUS_OK)           # same sha (any case)
        self.assertEqual(st["mod:z"], manifest.STATUS_OUTDATED)     # Drive zip replaced
        self.assertEqual(st["mod:old"], manifest.STATUS_OUTDATED)   # old mirror install
        self.assertEqual(st["mod:y"], manifest.STATUS_ERROR)        # no link yet
        self.assertNotIn("mod:r", st)

    def test_offline_and_no_build(self):
        def boom(p):
            raise DownloadError("no network")
        items = updater.check_updates(self.tmp, "linux", specs=[], log=lambda *a: None,
                                      resolve_unez=boom, resolve_fte=lambda p: None)
        st = {i.component: i.status for i in items}
        self.assertEqual(st["client:unez"], manifest.STATUS_ERROR)
        self.assertEqual(st["client:fte"], manifest.STATUS_UNAVAILABLE)

    def test_resolve_unez_picks_platform_asset_and_falls_back(self):
        rel = {"tag_name": "9.9", "assets": [
            {"name": "unezQuake-linux-x86_64.zip", "browser_download_url": "L", "size": 1},
            {"name": "unezQuake-windows-x64.zip", "browser_download_url": "W", "size": 2}]}
        m = clients.resolve_unez("linux", get_json=lambda u: rel)
        self.assertEqual((m["version"], m["url"]), ("9.9", "L"))
        no_linux = {"tag_name": "9.9", "assets": rel["assets"][1:]}
        self.assertIsNone(clients.resolve_unez("linux", get_json=lambda u: no_linux))

        def api_down(u):
            raise DownloadError("rate limited")
        m = clients.resolve_unez("windows", get_json=api_down,
                                 head=lambda u: {"url": u, "size": 3})
        self.assertTrue(m["url"].endswith("/unezQuake-windows-x64.zip"))


class ClientInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_update_keeps_user_cfgs(self):
        z = os.path.join(self.tmp, "fte.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("fteqw64.exe", "new-exe")
            zf.writestr("default.fmf", "game stock")
            zf.writestr("fte/config.cfg", "stock")
        dst = os.path.join(self.tmp, "FTE")
        os.makedirs(os.path.join(dst, "fte"))
        with open(os.path.join(dst, "fte", "config.cfg"), "w") as fh:
            fh.write("mine")
        with open(os.path.join(dst, "fteqw64.exe"), "w") as fh:
            fh.write("old-exe")
        exe, _files = clients.install_fte("windows", z, dst, os.path.join(self.tmp, "st"),
                                          log=lambda *a: None)
        self.assertEqual(exe, "fteqw64.exe")
        self.assertEqual(open(os.path.join(dst, "fteqw64.exe")).read(), "new-exe")
        self.assertEqual(open(os.path.join(dst, "fte", "config.cfg")).read(), "mine")
        self.assertEqual(open(os.path.join(dst, "default.fmf")).read(), "game stock")


if __name__ == "__main__":
    unittest.main()
