import os
import shutil
import tempfile
import unittest
import zipfile

from quake_installer import binds_mods, manifest, mods, settings, updater
from quake_installer.installer import Options, Reporter, Result, write_configs


def _quiet():
    r = Reporter()
    r.log = lambda *a: None
    return r


class SharedCfgInModsTests(unittest.TestCase):
    """Fix 1: name/binds/look reach every mod gamedir via id1/based.cfg."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mod_autoexec_execs_based_then_binds(self):
        o = Options(self.tmp, "Ranger", "soft", binds={"attack": "MOUSE1"},
                    mod_binds={"fortress": {"gren1": "g"}})
        for d in (os.path.join(o.fte_dir, "fortress"), os.path.join(o.unez_dir, "fortress")):
            os.makedirs(d)
        write_configs(o, _quiet(), Result())
        for tree in (o.fte_dir, o.unez_dir):
            based = open(os.path.join(tree, "id1", "based.cfg")).read()
            self.assertIn('name "Ranger"', based)
            self.assertIn("bind MOUSE1 +attack", based)
            self.assertIn("exec based.cfg", open(os.path.join(tree, "id1", "autoexec.cfg")).read())
            auto = open(os.path.join(tree, "fortress", "autoexec.cfg")).read()
            self.assertLess(auto.index("exec based.cfg"), auto.index("exec binds.cfg"))
            self.assertIn("bind g +gren1", open(os.path.join(tree, "fortress", "binds.cfg")).read())


class AirQuakeAutoexecTests(unittest.TestCase):
    """Fix 3: the mod's own AUTOEXEC.CFG is kept and merged, ending lowercase."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_merge_keeps_mod_lines_case_insensitive_and_idempotent(self):
        d = os.path.join(self.tmp, "airquake")
        os.makedirs(d)
        with open(os.path.join(d, "AUTOEXEC.CFG"), "w") as fh:
            fh.write("exec aqalias.cfg\r\nbind x liftcam\r\n")
        binds_mods.merge_mod_autoexec(d)
        # reinstall copies the mod's AUTOEXEC.CFG again: still one merged file
        with open(os.path.join(d, "AUTOEXEC.CFG"), "w") as fh:
            fh.write("exec aqalias.cfg\r\nbind x liftcam\r\n")
        binds_mods.merge_mod_autoexec(d)
        names = [n for n in os.listdir(d) if n.lower() == "autoexec.cfg"]
        self.assertEqual(names, ["autoexec.cfg"])
        text = open(os.path.join(d, "autoexec.cfg")).read().replace("\r\n", "\n")
        self.assertEqual(text.count("exec aqalias.cfg"), 1)
        self.assertEqual(text.count("exec based.cfg"), 1)
        self.assertEqual(text.count("exec binds.cfg"), 1)
        self.assertTrue(text.index("exec based.cfg") < text.index("bind x liftcam")
                        < text.index("exec binds.cfg"))


class PlatformUpdateTests(unittest.TestCase):
    """Updates never cross-install another OS's client builds."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_other_platform_install_skips_clients(self):
        m = manifest.empty("windows")
        manifest.record(m, "client:unez", {"version": "2.0.3"}, platform="windows")
        manifest.save(self.tmp, m)
        self.assertIn("Windows", updater.platform_mismatch_note(self.tmp, "linux"))
        self.assertEqual(updater.platform_mismatch_note(self.tmp, "windows"), "")
        seen = []
        items = updater.check_updates(self.tmp, "linux", specs=[], log=lambda *a: None,
                                      resolve_unez=lambda p: seen.append(p) or {"version": "9"},
                                      resolve_fte=lambda p: seen.append(p) or None)
        self.assertEqual(seen, [])  # nothing resolved for the other OS
        self.assertTrue(all(i.status == manifest.STATUS_PLATFORM and not i.needs_update
                            for i in items))


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        d = tempfile.mkdtemp()
        try:
            self.assertIsNone(settings.load(d))
            settings.save({"player_name": "Ranger", "binds": {"attack": "MOUSE1"},
                           "mod_binds": {"arena": {"stats": "i"}}, "platform": "linux"}, d)
            back = settings.load(d)
            self.assertEqual(back["binds"]["attack"], "MOUSE1")
            self.assertEqual(back["mod_binds"]["arena"]["stats"], "i")
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
