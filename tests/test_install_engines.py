"""Full installs with one engine selected (Settings: engines + custom folders)."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from quake_installer import installer, manifest


class Rep(object):
    def __init__(self):
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)

    def step(self, *args):
        pass

    def progress(self, *args):
        pass


class OptionsTests(unittest.TestCase):
    def test_unselected_engine_has_no_dir(self):
        opts = installer.Options("C:/Games", "p", "soft", platform="windows",
                                 install_unez=True, install_fte=False)
        self.assertEqual(opts.unez_dir, os.path.join("C:/Games", "unezQuake"))
        self.assertIsNone(opts.fte_dir)
        self.assertTrue(opts.install_unez)
        self.assertFalse(opts.install_fte)

    def test_custom_targets_win_over_the_root(self):
        opts = installer.Options("C:/Games", "p", "soft", platform="windows",
                                 install_unez=True, install_fte=True,
                                 unez_target="D:/ezquake", fte_target="E:/FTE")
        self.assertEqual(opts.unez_dir, "D:/ezquake")
        self.assertEqual(opts.fte_dir, "E:/FTE")


class UnezOnlyInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "Games")
        self.unez = os.path.join(self.tmp, "ezquake")
        self.rep = Rep()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unez_only_skips_fte_and_puts_mods_in_one_tree(self):
        opts = installer.Options(self.root, "p", "soft", platform="windows",
                                 install_unez=True, install_fte=False,
                                 unez_target=self.unez)
        spec = {"key": "painkeep", "title": "PainKeep", "gamedir": "painkeep",
                "clients": ["fte", "unez"], "version": "1", "sha256": "aa" * 32,
                "file": "painkeep.zip", "url": "u"}
        mod_calls = []

        def fake_unez(platform, zip_path, unez_dir, stage, **kwargs):
            os.makedirs(unez_dir, exist_ok=True)
            exe = "unezquake.exe"
            with open(os.path.join(unez_dir, exe), "w") as fh:
                fh.write("x")
            return exe, [exe]

        def fake_mod(s, fte_dir, work, **kwargs):
            mod_calls.append((fte_dir, kwargs.get("unez_dir")))
            for d in (fte_dir, kwargs.get("unez_dir")):
                if d:
                    os.makedirs(os.path.join(d, s["gamedir"]), exist_ok=True)
            kwargs["meta_out"].update({"file": s["file"], "version": s["version"],
                                       "sha256": s["sha256"], "size": 1})
            return "fake"

        def no_fte(*args, **kwargs):
            raise AssertionError("FTE was not selected but the installer touched it")

        with mock.patch.object(installer.clients, "resolve_unez",
                               return_value={"version": "2.1", "url": "u/unez.zip",
                                             "asset": "unez.zip"}), \
                mock.patch.object(installer.download, "download",
                                  side_effect=lambda url, path, **k: open(path, "w").close()), \
                mock.patch.object(installer.clients, "install_unez", fake_unez), \
                mock.patch.object(installer.clients, "resolve_fte", no_fte), \
                mock.patch.object(installer.clients, "install_fte", no_fte), \
                mock.patch.object(installer.extract, "pak0_is_valid", return_value=True), \
                mock.patch.object(installer.modlib, "load_specs_online",
                                  return_value=([spec], None)), \
                mock.patch.object(installer.modlib, "install_mod", fake_mod):
            res = installer.run_install(opts, self.rep)

        self.assertEqual(mod_calls, [(None, self.unez)])
        self.assertFalse(os.path.exists(os.path.join(self.root, "FTE")))
        self.assertEqual(res.unez_exe, "unezquake.exe")
        self.assertIsNone(res.fte_exe)
        comps = manifest.load(self.root)["components"]
        self.assertIn("client:unez", comps)
        self.assertNotIn("client:fte", comps)
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "id1", "based.cfg")))


if __name__ == "__main__":
    unittest.main()
