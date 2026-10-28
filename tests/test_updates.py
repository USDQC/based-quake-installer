import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

from quake_installer import clients, installer, manifest, updater
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
        manifest.record(m, "mod:y", {"file": "y.zip", "version": "1", "sha256": "dd" * 32})
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


class SelectionTests(unittest.TestCase):
    # CH - The dialog only lets users check rows apply_updates() can install, and the
    # default never picks "not installed" mods on its own.
    def _items(self):
        return [
            updater.UpdateItem("client:unez", "unezQuake", manifest.STATUS_OUTDATED),
            updater.UpdateItem("client:fte", "FTE", manifest.STATUS_OK),
            updater.UpdateItem("mod:a", "A", manifest.STATUS_OUTDATED),
            updater.UpdateItem("mod:b", "B", manifest.STATUS_MISSING),
            updater.UpdateItem("mod:c", "C", manifest.STATUS_ERROR),
            updater.UpdateItem("mod:d", "D", manifest.STATUS_UNAVAILABLE),
            updater.UpdateItem("client:old", "Old", manifest.STATUS_PLATFORM),
        ]

    def test_selectable_only_installable(self):
        got = {i.component for i in self._items() if updater.is_selectable(i)}
        self.assertEqual(got, {"client:unez", "mod:a", "mod:b"})

    def test_default_skips_missing(self):
        self.assertEqual(updater.select_components(self._items()),
                         {"client:unez", "mod:a"})

    def test_all_includes_missing_but_not_errors(self):
        self.assertEqual(updater.select_components(self._items(), updater.SELECT_MODE_ALL),
                         {"client:unez", "mod:a", "mod:b"})

    def test_engines_and_mods_presets(self):
        items = self._items()
        self.assertEqual(updater.select_components(items, updater.SELECT_MODE_ENGINES),
                         {"client:unez"})
        self.assertEqual(updater.select_components(items, updater.SELECT_MODE_MODS),
                         {"mod:a", "mod:b"})

    def test_none_and_unknown_mode(self):
        self.assertEqual(updater.select_components(self._items(), updater.SELECT_MODE_NONE),
                         set())
        with self.assertRaises(ValueError):
            updater.select_components(self._items(), "nope")


class _Rep(object):
    def __init__(self):
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)

    def step(self, *args):
        pass

    def progress(self, *args):
        pass


class ApplySubsetTests(unittest.TestCase):
    # CH - Selecting a subset must leave every unchecked component untouched.
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_selected_mods_are_installed(self):
        fte = os.path.join(self.tmp, "FTE")
        os.makedirs(fte)
        man = manifest.empty("windows")
        manifest.record(man, "mod:a", {"file": "a.zip", "version": "1",
                                       "sha256": "aa" * 32, "size": 10})
        manifest.record(man, "mod:b", {"file": "b.zip", "version": "1",
                                       "sha256": "bb" * 32, "size": 10})
        manifest.save(self.tmp, man)
        spec_a = {"key": "a", "title": "A", "gamedir": "a", "clients": ["fte"],
                  "version": "2", "sha256": "cc" * 32, "file": "a.zip", "url": "u"}
        item_a = updater.UpdateItem("mod:a", "A", manifest.STATUS_OUTDATED)
        item_a.spec = spec_a
        calls = []

        def fake_install(spec, fte_dir, work_dir, meta_out=None, **kwargs):
            calls.append(spec["key"])
            os.makedirs(os.path.join(fte_dir, spec["gamedir"]), exist_ok=True)
            meta_out.update({"file": spec["file"], "version": spec["version"],
                             "sha256": spec["sha256"], "size": 1})
            return "fake"

        opts = installer.Options(self.tmp, "p", "soft", platform="windows")
        with mock.patch.object(updater.modlib, "install_mod", fake_install):
            up, failed = updater.apply_updates(opts, [item_a], _Rep())
        self.assertEqual(calls, ["a"])
        self.assertEqual(failed, [])
        self.assertEqual([i.component for i in up], ["mod:a"])
        saved = manifest.load(self.tmp)["components"]
        self.assertEqual(saved["mod:a"]["version"], "2")
        self.assertEqual(saved["mod:b"]["version"], "1")

    def test_apply_skips_items_that_need_no_update(self):
        # An unchecked-but-outdated item never reaches apply_updates; an item passed
        # with status "up to date" must be a no-op.
        opts = installer.Options(self.tmp, "p", "soft", platform="windows")
        item = updater.UpdateItem("mod:a", "A", manifest.STATUS_OK)
        with mock.patch.object(updater.modlib, "install_mod",
                               side_effect=AssertionError("must not install")):
            up, failed = updater.apply_updates(opts, [item], _Rep())
        self.assertEqual((up, failed), ([], []))


class EngineFilterTests(unittest.TestCase):
    # CH - Check for updates follows the Settings engine choice: skipped engines get
    # no rows and their mods are not offered/updated.
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _opts(self, **kwargs):
        return installer.Options(self.tmp, "p", "soft", platform="windows", **kwargs)

    def _check(self, opts, specs):
        return updater.check_updates(
            self.tmp, "windows", specs=specs, log=lambda *a: None, opts=opts,
            resolve_unez=lambda p: {"version": "2.1", "url": "u"},
            resolve_fte=lambda p: {"version": "1.0", "url": "f"})

    def test_unselected_engine_has_no_row(self):
        items = self._check(self._opts(install_fte=False), [])
        self.assertEqual([i.component for i in items], ["client:unez"])

    def test_mods_for_unselected_engine_are_skipped(self):
        specs = [
            {"key": "fvf", "title": "FvF", "gamedir": "fvf", "clients": ["fte"],
             "version": "1", "url": "https://drive.google.com/file/d/x/view",
             "sha256": "aa" * 32},
            {"key": "painkeep", "title": "PainKeep", "gamedir": "painkeep",
             "clients": ["fte", "unez"], "version": "1",
             "url": "https://drive.google.com/file/d/p/view", "sha256": "bb" * 32},
        ]
        m = manifest.empty("windows")
        for k in ("fvf", "painkeep"):
            manifest.record(m, "mod:" + k, {"version": "0", "sha256": "00" * 32})
        manifest.save(self.tmp, m)
        items = self._check(self._opts(install_fte=False), specs)
        comps = [i.component for i in items]
        self.assertNotIn("mod:fvf", comps)
        self.assertIn("mod:painkeep", comps)

    def test_mod_presence_uses_custom_target_not_the_root(self):
        opts = self._opts(install_unez=True, install_fte=False,
                          unez_target=os.path.join(self.tmp, "ezquake"))
        spec = {"key": "painkeep", "gamedir": "painkeep", "clients": ["unez"]}
        os.makedirs(os.path.join(self.tmp, "ezquake", "painkeep"))
        open(os.path.join(self.tmp, "ezquake", "painkeep", "progs.dat"), "w").close()
        os.makedirs(os.path.join(self.tmp, "unezQuake", "painkeep"))
        open(os.path.join(self.tmp, "unezQuake", "painkeep", "progs.dat"), "w").close()
        self.assertTrue(updater._mod_present(self.tmp, spec, opts))
        # The default root tree is ignored when a custom target is configured.
        opts.unez_target = os.path.join(self.tmp, "elsewhere")
        self.assertFalse(updater._mod_present(self.tmp, spec, opts))

    def test_apply_updates_drops_unselected_engine(self):
        item = updater.UpdateItem("client:fte", "FTE", manifest.STATUS_OUTDATED)
        with mock.patch.object(updater.download, "download",
                               side_effect=AssertionError("must not download")):
            up, failed = updater.apply_updates(self._opts(install_fte=False), [item], _Rep())
        self.assertEqual((up, failed), ([], []))


class SummaryTests(unittest.TestCase):
    # CH - The dialog headline/group lines must never claim "up to date" when a
    # check failed, and missing mods stay separate from updates.
    def _item(self, component, status, title="T"):
        return updater.UpdateItem(component, title, status)

    def test_empty(self):
        self.assertEqual(updater.check_summary([]), ("Nothing to check.", []))

    def test_all_up_to_date(self):
        items = [self._item("client:unez", manifest.STATUS_OK),
                 self._item("client:fte", manifest.STATUS_OK),
                 self._item("mod:a", manifest.STATUS_OK),
                 self._item("mod:b", manifest.STATUS_OK)]
        headline, lines = updater.check_summary(items)
        self.assertEqual(headline, "Everything is up to date.")
        self.assertEqual(lines, ["Engines: unezQuake and FTE are up to date.",
                                 "Mods: all up to date (2)."])

    def test_mixed_updates_and_missing(self):
        items = [self._item("client:unez", manifest.STATUS_OUTDATED),
                 self._item("client:fte", manifest.STATUS_OK),
                 self._item("mod:a", manifest.STATUS_OUTDATED),
                 self._item("mod:b", manifest.STATUS_MISSING)]
        headline, lines = updater.check_summary(items)
        self.assertEqual(headline, "Updates available.")
        self.assertEqual(lines, ["Engines: unezQuake update available; FTE up to date.",
                                 "Mods: 1 update available, 1 not installed."])

    def test_issues_only_never_says_up_to_date(self):
        items = [self._item("client:fte", manifest.STATUS_ERROR),
                 self._item("mod:a", manifest.STATUS_UNAVAILABLE),
                 self._item("mod:b", manifest.STATUS_PLATFORM)]
        headline, lines = updater.check_summary(items)
        self.assertEqual(headline,
                         "No updates available, but some checks need attention.")
        self.assertIn("Engines: FTE check failed.", lines)
        self.assertIn("Mods: 1 without a build for this platform, "
                      "1 for another platform.", lines)

    def test_mods_only_has_no_engine_line(self):
        headline, lines = updater.check_summary(
            [self._item("mod:a", manifest.STATUS_OUTDATED)])
        self.assertEqual(headline, "Updates available.")
        self.assertEqual(lines, ["Mods: 1 update available."])

    def test_one_engine_uses_is(self):
        headline, lines = updater.check_summary(
            [self._item("client:fte", manifest.STATUS_OK)])
        self.assertEqual(headline, "Everything is up to date.")
        self.assertEqual(lines, ["Engines: FTE is up to date."])


if __name__ == "__main__":
    unittest.main()


class NotInstalledModsTests(unittest.TestCase):
    """Mods the user left unticked are never offered as updates."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_installed_mods_are_listed(self):
        m = manifest.empty("windows")
        manifest.record(m, "mod:a", {"version": "1", "sha256": "aa" * 32})
        manifest.save(self.tmp, m)
        os.makedirs(os.path.join(self.tmp, "FTE", "c", "maps"))  # on disk, no record
        with open(os.path.join(self.tmp, "FTE", "c", "maps", "m.bsp"), "wb") as fh:
            fh.write(b"x")
        url = "https://drive.google.com/file/d/q/view"
        specs = [{"key": k, "title": k, "gamedir": k, "clients": ["fte"], "version": "2",
                  "url": url, "sha256": "bb" * 32} for k in ("a", "b", "c")]
        opts = installer.Options(self.tmp, "p", "soft", platform="windows",
                                 install_unez=False)
        items = updater.check_updates(
            self.tmp, "windows", specs=specs, log=lambda *a: None, opts=opts,
            resolve_fte=lambda p: {"version": "1.0", "url": "f"})
        st = {i.component: i.status for i in items}
        self.assertEqual(st["mod:a"], manifest.STATUS_OUTDATED)
        self.assertNotIn("mod:b", st)        # never installed: not an update
        self.assertIn("mod:c", st)           # present on disk counts as installed
        self.assertFalse(any(i.status == manifest.STATUS_MISSING
                             for i in items if i.component.startswith("mod:")))
