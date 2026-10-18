import os, shutil, tempfile, unittest
from quake_installer import binds_mods, cfg, extract, installer


class Rep(object):
    def __init__(self): self.lines = []
    def log(self, m): self.lines.append(m)


class UnknownModBindTests(unittest.TestCase):
    def test_unknown_listed(self):
        self.assertEqual(binds_mods.unknown_mod_bind_actions(
            "runequake", {"use": "r", "rune_use": "u", "blank": ""}), ["use"])

    def test_logged_once_and_known_written(self):
        tmp = tempfile.mkdtemp()
        try:
            for c in ("FTE", "unezQuake"):
                os.makedirs(os.path.join(tmp, c, "runequake"))
            o = installer.Options(tmp, "Ranger", "soft", binds={},
                                  mod_binds={"runequake": {"use": "r", "rune_use": "u"}})
            rep = Rep()
            installer.write_mod_configs(o, rep, installer.Result())
            hits = [l for l in rep.lines if "unknown action" in l]
            self.assertEqual(len(hits), 1)
            self.assertIn("WARN", hits[0])
            txt = open(os.path.join(tmp, "FTE", "runequake", "binds.cfg")).read()
            self.assertIn('bind u "impulse 100"', txt)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class NoteLabelTests(unittest.TestCase):
    def test_registered_note_is_note(self):
        src = open(installer.__file__).read()
        self.assertIn('rep.log("  NOTE: %s" % spec.get("note"', src)
        self.assertNotIn('rep.log("  WARN: %s" % spec.get("note"', src)


class EngineCvarTests(unittest.TestCase):
    def test_unez_uses_ezquake_names(self):
        for look in ("soft", "gl"):
            t = cfg.render_autoexec(cfg.CLIENT_UNEZ, "Ranger", {}, look)
            for bad in ("mlook_enabled", "r_particles ", "r_particle_type",
                        "anisotropicfilter_extent"):
                self.assertNotIn(bad, t)
            self.assertIn("freelook 1", t)
            self.assertIn("gl_anisotropy", t)

    def test_fte_keeps_mlook_enabled(self):
        self.assertIn("mlook_enabled 1", cfg.render_autoexec(cfg.CLIENT_FTE, "Ranger", {}, "gl"))


@unittest.skipIf(os.name == "nt", "case-insensitive FS")
class LowercaseTreeTests(unittest.TestCase):
    def setUp(self): self.t = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.t, ignore_errors=True)

    def _w(self, rel, data):
        p = os.path.join(self.t, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(data)

    def test_renames_and_merges(self):
        self._w("PAK0.PAK", "p"); self._w("GFX/CONBACK.LMP", "c"); self._w("gfx/x.lmp", "x")
        self._w("CLAN.TXT", "new"); self._w("clan.txt", "old")
        extract.lowercase_tree(self.t, incoming_wins=True)
        self.assertEqual(sorted(os.listdir(self.t)), ["clan.txt", "gfx", "pak0.pak"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.t, "gfx"))), ["conback.lmp", "x.lmp"])
        self.assertEqual(open(os.path.join(self.t, "clan.txt")).read(), "new")

    def test_existing_wins(self):
        self._w("PAK0.PAK", "stale"); self._w("pak0.pak", "fresh")
        extract.lowercase_tree(self.t, incoming_wins=False)
        self.assertEqual(os.listdir(self.t), ["pak0.pak"])
        self.assertEqual(open(os.path.join(self.t, "pak0.pak")).read(), "fresh")
