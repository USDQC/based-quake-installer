"""Mod binds also load when a server switches the client into the mod gamedir."""
import os
import shutil
import struct
import tempfile
import unittest
import zipfile

from quake_installer import binds_mods, installer


def _pak(path, names):
    """Minimal PACK file with empty entries."""
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4sii", b"PACK", 12, 64 * len(names)))
        for n in names:
            fh.write(n.encode().ljust(56, b"\0") + struct.pack("<ii", 0, 0))


class Rep:
    def __init__(self):
        self.lines = []

    def log(self, s):
        self.lines.append(s)


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


class SwitchHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gd(self, name):
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        return d

    def test_fte_quake_rc_when_no_trigger(self):
        d = self.gd("ctf")
        _pak(os.path.join(d, "pak0.pak"), ["progs/v_airgun.mdl", "maps/twctf1.bsp"])
        p = binds_mods.ensure_switch_hook(d, "FTE")
        self.assertEqual(p, os.path.join(d, "quake.rc"))
        t = _read(p)
        for line in ("exec default.cfg", "exec config.cfg", "exec autoexec.cfg", "stuffcmds"):
            self.assertIn(line + "\r\n", t)
        self.assertNotIn("startdemos", t)
        self.assertFalse(os.path.exists(os.path.join(d, "frontend.cfg")))

    def test_fte_trigger_in_pak_any_case(self):
        for name in ("QUAKE.RC", "default.cfg", "Server.cfg", "hexen.rc"):
            d = self.gd("m_" + name.replace(".", "_"))
            _pak(os.path.join(d, "PAK0.PAK"), ["progs/x.mdl", name])
            self.assertTrue(binds_mods.mod_has_fte_reload_trigger(d), name)
            self.assertIsNone(binds_mods.ensure_switch_hook(d, "FTE"))
            self.assertEqual(binds_mods._find_ci(d, "quake.rc"), [])

    def test_fte_trigger_in_pk3_and_loose(self):
        d = self.gd("pk3mod")
        with zipfile.ZipFile(os.path.join(d, "zz.pk3"), "w") as z:
            z.writestr("Default.cfg", "bind x y\n")
        self.assertIsNone(binds_mods.ensure_switch_hook(d, "FTE"))
        d2 = self.gd("loose")
        with open(os.path.join(d2, "SERVER.CFG"), "w") as fh:
            fh.write("map start\n")
        self.assertIsNone(binds_mods.ensure_switch_hook(d2, "FTE"))

    def test_fte_mod_quake_rc_never_overwritten(self):
        d = self.gd("airquake")
        with open(os.path.join(d, "quake.rc"), "w") as fh:
            fh.write("exec default.cfg\nexec autoexec.cfg\nstartdemos demo1\n")
        self.assertIsNone(binds_mods.ensure_switch_hook(d, "FTE"))
        self.assertIn("startdemos", _read(os.path.join(d, "quake.rc")))

    def test_fte_idempotent_and_removed_when_mod_gains_trigger(self):
        d = self.gd("arena")
        p = binds_mods.ensure_switch_hook(d, "FTE")
        first = _read(p)
        self.assertFalse(binds_mods.mod_has_fte_reload_trigger(d))  # ours doesn't count
        self.assertEqual(binds_mods.ensure_switch_hook(d, "FTE"), p)
        self.assertEqual(_read(p), first)
        _pak(os.path.join(d, "pak1.pak"), ["default.cfg"])
        self.assertIsNone(binds_mods.ensure_switch_hook(d, "FTE"))
        self.assertFalse(os.path.exists(p))

    def test_bad_archive_ignored(self):
        d = self.gd("junk")
        with open(os.path.join(d, "pak0.pak"), "wb") as fh:
            fh.write(b"not a pak")
        with open(os.path.join(d, "bad.pk3"), "wb") as fh:
            fh.write(b"not a zip")
        self.assertFalse(binds_mods.mod_has_fte_reload_trigger(d))

    def test_unez_frontend(self):
        d = self.gd("ctf")
        p = binds_mods.ensure_switch_hook(d, "unezQuake")
        self.assertEqual(p, os.path.join(d, "frontend.cfg"))
        self.assertIn("exec autoexec.cfg\r\n", _read(p))
        self.assertEqual(binds_mods.ensure_switch_hook(d, "unezQuake"), p)
        self.assertEqual(_read(p).count("exec autoexec.cfg"), 1)
        self.assertFalse(os.path.exists(os.path.join(d, "quake.rc")))

    def test_unez_mod_frontend_kept_and_extended(self):
        d = self.gd("mod")
        with open(os.path.join(d, "frontend.cfg"), "w") as fh:
            fh.write("echo mod frontend\n")
        p = binds_mods.ensure_switch_hook(d, "unezQuake")
        t = _read(p)
        self.assertTrue(t.startswith("echo mod frontend"))
        self.assertEqual(t.count("exec autoexec.cfg"), 1)
        binds_mods.ensure_switch_hook(d, "unezQuake")
        self.assertEqual(_read(p).count("exec autoexec.cfg"), 1)

    def test_missing_dir_and_unknown_client(self):
        self.assertIsNone(binds_mods.ensure_switch_hook(os.path.join(self.tmp, "nope"), "FTE"))
        self.assertIsNone(binds_mods.ensure_switch_hook(self.gd("x"), "other"))

    def test_write_mod_configs_per_client(self):
        o = installer.Options(self.tmp, "Ranger", "soft", binds={},
                              mod_binds={"thunderwalker": {"q_airfist": "f"}})
        fte_ctf = os.path.join(o.fte_dir, "ctf")
        unez_ctf = os.path.join(o.unez_dir, "ctf")
        fte_pk = os.path.join(o.fte_dir, "painkeep")
        for d in (fte_ctf, unez_ctf, fte_pk):
            os.makedirs(d)
        _pak(os.path.join(fte_pk, "pak0.pak"), ["quake.rc", "default.cfg"])
        res = installer.Result()
        installer.write_mod_configs(o, Rep(), res)
        self.assertTrue(os.path.isfile(os.path.join(fte_ctf, "quake.rc")))
        self.assertFalse(os.path.exists(os.path.join(fte_ctf, "frontend.cfg")))
        self.assertTrue(os.path.isfile(os.path.join(unez_ctf, "frontend.cfg")))
        self.assertFalse(os.path.exists(os.path.join(unez_ctf, "quake.rc")))
        self.assertEqual(binds_mods._find_ci(fte_pk, "quake.rc"), [])
        # going back to a base server in unezQuake re-runs the base autoexec
        qw = os.path.join(o.unez_dir, "qw", "frontend.cfg")
        self.assertIn("exec autoexec.cfg", _read(qw))
        self.assertIn(qw, res.cfg_files)
        # nothing written in FTE's base folders
        for base in ("id1", "qw", "fte"):
            for n in ("quake.rc", "frontend.cfg"):
                self.assertFalse(os.path.exists(os.path.join(o.fte_dir, base, n)))
        # the chain the hooks rely on is still there
        self.assertIn("exec binds.cfg", _read(os.path.join(fte_ctf, "autoexec.cfg")))
        self.assertIn("bind f +bqi_airfist", _read(os.path.join(unez_ctf, "binds.cfg")))


if __name__ == "__main__":
    unittest.main()
