import os, shutil, tempfile, unittest
from quake_installer import binds_mods, cfg


def _r(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


class UnezConfigCfg(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = os.path.join(self.tmp, "hh")
        os.makedirs(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_base_sets_legacy_exec(self):
        self.assertIn("cfg_legacy_exec 1", cfg.CLIENT_BASE["unez"])
        self.assertNotIn("cfg_legacy_exec", cfg.CLIENT_BASE.get("fte", ""))

    def test_new_file_idempotent(self):
        p = binds_mods.ensure_unez_config_cfg(self.d)
        self.assertEqual(p, os.path.join(self.d, "config.cfg"))
        binds_mods.ensure_unez_config_cfg(self.d)
        t = _r(p)
        self.assertEqual(t.count("exec autoexec.cfg"), 1)
        self.assertIn("Based Quake Installer", t)

    def test_mod_shipped_kept_case_insensitive(self):
        with open(os.path.join(self.d, "CONFIG.CFG"), "w") as fh:
            fh.write("echo mod")
        p = binds_mods.ensure_unez_config_cfg(self.d)
        self.assertEqual(os.path.basename(p), "CONFIG.CFG")
        binds_mods.ensure_unez_config_cfg(self.d)
        t = _r(p)
        self.assertTrue(t.startswith("echo mod\n"))
        self.assertEqual(t.count("exec autoexec.cfg"), 1)
        self.assertFalse(os.path.exists(os.path.join(self.d, "config.cfg")) and
                         "config.cfg" in os.listdir(self.d))

    def test_autoexec_never_execs_root_config(self):
        with open(os.path.join(self.d, "autoexec.cfg"), "w") as fh:
            fh.write("exec based.cfg\nexec config.cfg\nexec configs/config.cfg\n")
        binds_mods.ensure_unez_config_cfg(self.d)
        binds_mods.ensure_unez_config_cfg(self.d)
        lines = [l.strip().lower() for l in _r(os.path.join(self.d, "autoexec.cfg")).splitlines()]
        self.assertNotIn("exec config.cfg", lines)
        self.assertIn("exec configs/config.cfg", lines)

    def test_missing_dir(self):
        self.assertIsNone(binds_mods.ensure_unez_config_cfg(os.path.join(self.tmp, "nope")))


if __name__ == "__main__":
    unittest.main()
