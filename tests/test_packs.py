"""Skin and spray packs: qw/skins (both clients), qw/sprays (unezQuake only)."""
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile

from quake_installer import cfg, installer, manifest, mods, updater


def _zip(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        for n, data in entries.items():
            z.writestr(n, data)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return h, os.path.getsize(path)


class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fte = os.path.join(self.tmp, "FTE")
        self.unez = os.path.join(self.tmp, "unezQuake")
        self.specs = {m["key"]: dict(m) for m in mods.MODS}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install(self, key, entries):
        spec = self.specs[key]
        z = os.path.join(self.tmp, spec["file"])
        spec["sha256"], spec["size"] = _zip(z, entries)
        return mods.install_mod(spec, self.fte, os.path.join(self.tmp, "w"),
                                log=lambda *a: None, local_file=z, unez_dir=self.unez)

    def test_specs(self):
        s, p = self.specs["skins"], self.specs["sprays"]
        self.assertTrue(mods.is_pack(s) and mods.is_pack(p))
        self.assertEqual((s["gamedir"], s["subdir"], s["file"]), ("qw", "skins", "skins.zip"))
        self.assertEqual(set(s["clients"]), {"fte", "unez"})
        self.assertEqual((p["gamedir"], p["subdir"], p["file"]), ("qw", "sprays", "sprays.zip"))
        self.assertEqual(p["clients"], ["unez"])
        self.assertIn("1L4NKfzkWWhKY9qRUWLgdpXZA-XePOiWs", s["url"])
        self.assertIn("1WsydUDZwaZzPTwvxCIzxpEta0PyPFCkx", p["url"])

    def test_skins_both_clients_keep_user_files(self):
        for root in (self.fte, self.unez):
            os.makedirs(os.path.join(root, "qw", "skins"))
            with open(os.path.join(root, "qw", "skins", "mine.pcx"), "wb") as fh:
                fh.write(b"user")
            with open(os.path.join(root, "qw", "skins", "heman.pcx"), "wb") as fh:
                fh.write(b"old")
            with open(os.path.join(root, "qw", "Config.CFG"), "w") as fh:
                fh.write("keep")
        self._install("skins", {"qw/skins/heman.pcx": b"new", "qw/skins/doom.png": b"png"})
        for root in (self.fte, self.unez):
            d = os.path.join(root, "qw", "skins")
            self.assertEqual(sorted(os.listdir(d)), ["doom.png", "heman.pcx", "mine.pcx"])
            self.assertEqual(open(os.path.join(d, "mine.pcx"), "rb").read(), b"user")
            self.assertEqual(open(os.path.join(d, "heman.pcx"), "rb").read(), b"new")
            # nothing else in qw/ renamed or touched
            self.assertTrue(os.path.isfile(os.path.join(root, "qw", "Config.CFG")))
            self.assertTrue(mods.is_present(self.specs["skins"], root + "/qw"))

    def test_reinstall_is_safe(self):
        e = {"qw/skins/cop.pcx": b"x"}
        self._install("skins", e)
        self._install("skins", e)
        self.assertEqual(os.listdir(os.path.join(self.fte, "qw", "skins")), ["cop.pcx"])

    def test_sprays_unez_only(self):
        self._install("sprays", {"qw/sprays/usdqc.png": b"p"})
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "qw", "sprays", "usdqc.png")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", "sprays")))

    def test_only_pack_folder_images_copied(self):
        self._install("skins", {"qw/skins/a.pcx": b"a", "qw/skins/readme.txt": b"t",
                                "qw/autoexec.cfg": b"evil", "qw/progs.dat": b"x"})
        self.assertEqual(os.listdir(os.path.join(self.fte, "qw", "skins")), ["a.pcx"])
        self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", "autoexec.cfg")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", "progs.dat")))

    def test_bad_sha_and_empty_pack_refused(self):
        spec = self.specs["skins"]
        z = os.path.join(self.tmp, "skins.zip")
        _zip(z, {"qw/skins/a.pcx": b"a"})
        spec["sha256"], spec["size"] = "0" * 64, os.path.getsize(z)
        with self.assertRaises(mods.ModError):
            mods.install_mod(spec, self.fte, self.tmp + "/w", log=lambda *a: None,
                             local_file=z, unez_dir=self.unez)
        self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", "skins")))
        with self.assertRaises(mods.ModError):
            self._install("skins", {"qw/maps/x.bsp": b"m"})

    def test_no_mod_configs_written_in_qw(self):
        self._install("skins", {"qw/skins/a.pcx": b"a"})
        o = installer.Options(self.tmp, "Ranger", "soft", binds={}, mod_binds={})
        installer.write_mod_configs(o, type("R", (), {"log": lambda s, m: None})(),
                                    installer.Result())
        for n in ("autoexec.cfg", "binds.cfg", "quake.rc"):
            self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", n)), n)

    def test_placeholder_never_overrides_and_index_sets_link(self):
        url = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/view"
        specs = mods.load_specs({"mods": [
            {"key": "skins", "url": url, "sha256": "a" * 64, "size": 5},
            {"key": "sprays", "url": "PASTE_DRIVE_LINK", "sha256": ""}]})
        by = {m["key"]: m for m in specs}
        self.assertEqual(by["skins"]["url"], url)
        self.assertEqual(by["skins"]["sha256"], "a" * 64)
        self.assertEqual(by["sprays"]["url"], self.specs["sprays"]["url"])
        self.assertEqual(by["sprays"]["sha256"], self.specs["sprays"]["sha256"])
        self.assertTrue(mods.is_pack(by["skins"]))

    def test_update_check_lists_packs(self):
        os.makedirs(os.path.join(self.unez, "qw", "sprays"))
        open(os.path.join(self.unez, "qw", "sprays", "usdqc.png"), "wb").close()
        self.assertTrue(updater._mod_present(self.tmp, self.specs["sprays"]))
        self.assertFalse(updater._mod_present(self.tmp, self.specs["skins"]))

    def test_drive_mods_json_matches(self):
        p = "/workspace/drive-upload/mods.json"
        if not os.path.isfile(p):
            self.skipTest("no drive-upload")
        by = {m["key"]: m for m in json.load(open(p))["mods"]}
        for k in ("skins", "sprays"):
            self.assertEqual(by[k]["sha256"], self.specs[k]["sha256"])
            self.assertEqual(by[k]["size"], self.specs[k]["size"])
            self.assertEqual(by[k]["url"], self.specs[k]["url"])
        self.assertEqual(len(by), 11)

    def test_based_cfg_spray_image(self):
        u = cfg.render_autoexec(cfg.CLIENT_UNEZ, "Ranger", {}, "soft")
        f = cfg.render_autoexec(cfg.CLIENT_FTE, "Ranger", {}, "soft")
        self.assertIn("cl_spray_image usdqc", u)
        self.assertNotIn("spray", f)


if __name__ == "__main__":
    unittest.main()
