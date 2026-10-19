"""Offline unit tests:  python -m unittest discover -s tests -v"""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quake_installer import cfg, launchers, mods, extract, lha  # noqa: E402
from quake_installer.installer import (  # noqa: E402
    Options, Reporter, write_configs, Result, cfg_targets, resolve_mod_keys, all_mod_keys,
)


class CfgTests(unittest.TestCase):
    def binds_map(self, text):
        out = {}
        for line in text.splitlines():
            if line.startswith("bind "):
                key = line.split()[1].lower()
                self.assertNotIn(key, out, "duplicate bind for %s" % key)
                out[key] = line
        return out

    def test_blank_binds_only_stock_misc(self):
        t = cfg.render_autoexec(cfg.CLIENT_FTE, "Ranger", {}, "soft")
        self.assertIn('name "Ranger"', t)
        self.assertIn("unbindall", t)
        b = self.binds_map(t)
        self.assertIn("escape", b)
        self.assertNotIn("w", b)
        self.assertNotIn("1", b)

    def test_custom_binds_and_validation(self):
        binds = {"forward": "w", "jump": "SPACE", "attack": "MOUSE1", "impulse1": "1"}
        t = cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", binds, "gl")
        b = self.binds_map(t)
        self.assertEqual(b["w"], "bind w +forward")
        self.assertEqual(b["space"], "bind SPACE +jump")
        self.assertEqual(b["mouse1"], "bind MOUSE1 +attack")
        self.assertEqual(b["1"], 'bind 1 "impulse 1"')
        self.assertIn("gl_anisotropy 8", t)
        self.assertEqual(cfg.normalize_key(" mouse1 "), "MOUSE1")
        self.assertEqual(cfg.normalize_key("Ctrl"), "CTRL")
        with self.assertRaises(ValueError):
            cfg.normalize_key('a;quit')
        with self.assertRaises(ValueError):
            cfg.normalize_key('a b')

    def test_presets_fill_dicts(self):
        v = cfg.PRESET_VANILLA
        self.assertEqual(v["forward"], "UPARROW")
        self.assertEqual(cfg.PRESET_WASD["forward"], "w")
        self.assertEqual(cfg.PRESET_MODERN["impulse2"], "q")
        legacy = cfg.binds_from_legacy("wasd", "modern")
        self.assertEqual(legacy["forward"], "w")
        self.assertEqual(legacy["impulse7"], "r")

    def test_name_quotes_escaped(self):
        t = cfg.render_autoexec(cfg.CLIENT_FTE, 'Ranger "The" R\n;quit', {}, "soft")
        self.assertIn('name "Ranger \'The\' R;quit"', t)
        self.assertEqual(cfg.sanitize_name("   "), "player")
        self.assertEqual(len(cfg.sanitize_name("x" * 80)), 31)

    def test_look_blocks_are_client_specific(self):
        fs = cfg.render_autoexec(cfg.CLIENT_FTE, "p", {}, "soft")
        fg = cfg.render_autoexec(cfg.CLIENT_FTE, "p", {}, "gl")
        us = cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", {}, "soft")
        ug = cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", {}, "gl")
        self.assertIn("r_softwarebanding 1", fs)
        self.assertIn("vid_renderer gl", fg)
        self.assertIn("r_bloom 0", us)
        self.assertNotIn("r_softwarebanding", us)
        self.assertIn("gl_anisotropy 8", ug)

    def test_duplicate_keys_later_action_wins(self):
        # Two actions mapped to same key: later BIND_ACTIONS entry wins.
        binds = {"attack": "MOUSE1", "jump": "MOUSE1"}
        b = self.binds_map(cfg.render_autoexec(cfg.CLIENT_FTE, "p", binds, "soft"))
        self.assertEqual(b["mouse1"], "bind MOUSE1 +jump")

    def test_qw_bind_actions_and_vanilla_preset(self):
        ids = [a[0] for a in cfg.BIND_ACTIONS]
        self.assertIn("changeweapon", ids)
        self.assertIn("mouse_mlook", ids)
        self.assertIn("showscores", ids)  # v1.6.5: Show scoreboard, Default = TAB
        self.assertNotIn("mouse_attack", ids)
        self.assertNotIn("messagemode", ids)
        self.assertEqual(cfg.ACTION_BY_ID["changeweapon"][1], "impulse 10")
        self.assertEqual(cfg.PRESET_VANILLA["attack"], "CTRL")
        self.assertEqual(cfg.PRESET_VANILLA["changeweapon"], "/")
        self.assertEqual(cfg.PRESET_VANILLA["mouse_mlook"], "\\")
        t = cfg.render_autoexec(cfg.CLIENT_FTE, "p", cfg.PRESET_VANILLA, "soft")
        b = self.binds_map(t)
        self.assertEqual(b["ctrl"], "bind CTRL +attack")
        self.assertIn('bind / "impulse 10"', b["/"])


class InstallLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_separate_cfg_files_per_tree(self):
        o = Options(self.tmp, "Ranger", "gl", binds=cfg.binds_from_legacy("wasd", "modern"))
        r = Result()
        rep = Reporter()
        rep.log = lambda m: None
        write_configs(o, rep, r)
        fte, unez = cfg_targets(o)
        for p in fte + unez:
            self.assertTrue(os.path.isfile(p), p)
        for p in (fte[1], unez[1]):
            with open(p) as fh:
                self.assertIn("exec based.cfg", fh.read())
        based = [os.path.join(os.path.dirname(p), "based.cfg") for p in (fte[1], unez[1])]
        with open(based[0]) as a, open(based[1]) as b:
            ta, tb = a.read(), b.read()
        self.assertNotEqual(ta, tb)
        self.assertIn("vid_renderer gl", ta)
        self.assertIn("gl_anisotropy 8", tb)

    def test_resolve_mods_defaults_to_all(self):
        o = Options(self.tmp, "p", "soft", mods=None)
        self.assertEqual(resolve_mod_keys(o), all_mod_keys())
        o2 = Options(self.tmp, "p", "soft", mods=[])
        self.assertEqual(resolve_mod_keys(o2), all_mod_keys())
        o3 = Options(self.tmp, "p", "soft", mods=["fortress"])
        self.assertEqual(resolve_mod_keys(o3), ["fortress"])


class LauncherTests(unittest.TestCase):
    def test_fte_args_always_nohome_basedir(self):
        a = launchers.fte_args(r"C:\Games\FTE")
        self.assertEqual(a[0], "-nohome")
        self.assertEqual(a[1], "-basedir")
        a = launchers.fte_args(r"C:\Games\FTE", game="airquake")
        self.assertIn("-nohome", a)
        self.assertIn("-basedir", a)
        self.assertEqual(a[-2:], ["-game", "airquake"])
        s = launchers.fte_args_string("/x/FTE/", game="hh")
        self.assertTrue(s.startswith('-nohome -basedir "'))
        self.assertTrue(s.endswith(" -game hh"))
        self.assertNotIn('/"', s)

    def test_ensure_fte_default_fmf_writes_disablehomedir(self):
        d = tempfile.mkdtemp()
        try:
            logs = []
            path = launchers.ensure_fte_default_fmf(d, log=logs.append)
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("disablehomedir 1", body.lower())
            # Second call is a no-op when already set
            logs2 = []
            launchers.ensure_fte_default_fmf(d, log=logs2.append)
            self.assertTrue(any("already" in x.lower() for x in logs2))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_ensure_fte_default_fmf_patches_existing(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "default.fmf")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("FTEManifestVer 1\ngame afterquake\nname \"AfterQuake\"\n"
                         "basegame id1\n")
            launchers.ensure_fte_default_fmf(d, log=lambda m: None)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertRegex(body, r"(?im)^\s*disablehomedir\s+1\b")
            self.assertIn("game afterquake", body)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ModTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mk(self, rel):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write("x")

    def test_specs_and_clients(self):
        keys = {m["key"]: m for m in mods.load_specs()}
        self.assertEqual(set(keys), {
            "airquake", "painkeep", "hh", "fortress", "thunderwalker", "arena",
            "fvf", "rally", "grq", "runequake"})
        self.assertEqual(set(keys["runequake"]["clients"]), {"fte", "unez"})
        self.assertEqual(keys["runequake"]["gamedir"], "runequake")
        self.assertEqual(set(keys["grq"]["clients"]), {"fte", "unez"})
        self.assertEqual(keys["grq"]["gamedir"], "grq")
        self.assertTrue(keys["grq"]["needs_registered"])
        self.assertNotIn("rangerhq", keys)
        self.assertNotIn("slipgate", keys)
        self.assertEqual(keys["airquake"]["clients"], ["fte"])
        self.assertEqual(keys["fvf"]["clients"], ["fte"])
        self.assertEqual(keys["rally"]["clients"], ["fte"])
        self.assertEqual(set(keys["painkeep"]["clients"]), {"fte", "unez"})
        self.assertEqual(set(keys["hh"]["clients"]), {"fte", "unez"})
        self.assertEqual(set(keys["fortress"]["clients"]), {"fte", "unez"})
        self.assertEqual(set(keys["thunderwalker"]["clients"]), {"fte", "unez"})
        self.assertEqual(set(keys["arena"]["clients"]), {"fte", "unez"})
        self.assertEqual(keys["fortress"]["gamedir"], "fortress")
        self.assertEqual(keys["thunderwalker"]["gamedir"], "ctf")
        self.assertEqual(keys["arena"]["gamedir"], "arena")
        self.assertEqual(keys["fvf"]["gamedir"], "fvf")
        self.assertEqual(keys["rally"]["gamedir"], "rally")
        dirs = mods.client_dirs(keys["fvf"], "/fte", "/unez")
        self.assertEqual(dirs, [("FTE", os.path.join("/fte", "fvf"))])
        dirs = mods.client_dirs(keys["fortress"], "/fte", "/unez")
        self.assertEqual([d[0] for d in dirs], ["FTE", "unezQuake"])

    def test_runequake_binds_only_install(self):
        spec = [m for m in mods.MODS if m["key"] == "runequake"][0]
        self.assertFalse(spec["needs_registered"])
        fte, unez = os.path.join(self.tmp, "FTE"), os.path.join(self.tmp, "unez")
        src = mods.install_mod(spec, fte, os.path.join(self.tmp, "w"), log=lambda *a: None,
                               unez_dir=unez)
        self.assertTrue(src.startswith("binds only"))
        for t in (fte, unez):
            d = os.path.join(t, "runequake")
            self.assertEqual(sorted(os.listdir(d)), ["autoexec.cfg", "binds.cfg"])
            with open(os.path.join(d, "autoexec.cfg")) as fh:
                self.assertIn("exec binds.cfg", fh.read())

    def test_zip_slip_rejected(self):
        z = os.path.join(self.tmp, "bad.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("../evil.txt", "x")
        with self.assertRaises(extract.ExtractError):
            extract.safe_extract_zip(z, os.path.join(self.tmp, "out"))



class ModBindTests(unittest.TestCase):
    def test_schema_has_researched_mods(self):
        from quake_installer import binds_mods
        keys = set(binds_mods.MOD_BIND_ACTIONS)
        self.assertTrue({"fortress", "thunderwalker", "arena", "painkeep",
                         "airquake", "rally", "grq", "runequake"} <= keys)
        self.assertEqual(binds_mods.action_by_id("runequake")["rune_use"][1], "impulse 100")
        self.assertEqual(binds_mods.action_by_id("grq")["cashbox"][1], "impulse 120")
        self.assertIn("hh", binds_mods.MOD_BIND_SKIP)
        self.assertIn("fvf", binds_mods.MOD_BIND_SKIP)
        gren = [a for a in binds_mods.actions_for("fortress") if a[0] == "gren1"][0]
        self.assertEqual(gren[1], "+gren1")
        hook = [a for a in binds_mods.actions_for("thunderwalker") if a[0] == "hook"][0]
        self.assertEqual(hook[1], "impulse 22")

    def test_render_mod_binds_and_write(self):
        from quake_installer import binds_mods
        text = binds_mods.render_mod_binds_cfg(
            "fortress", {"gren1": "c", "special": "v", "hook": "MOUSE2"})
        self.assertIn("bind c +gren1", text)
        self.assertIn("bind v special", text)
        self.assertIn('bind MOUSE2 "impulse 22"', text)
        self.assertNotIn("\nunbindall", "\n" + text.replace("\r", ""))
        d = tempfile.mkdtemp()
        try:
            auto = os.path.join(d, "autoexec.cfg")
            self.assertTrue(binds_mods.ensure_autoexec_execs_binds(auto))
            with open(auto) as fh:
                body = fh.read()
            self.assertIn("exec binds.cfg", body)
            self.assertFalse(binds_mods.ensure_autoexec_execs_binds(auto))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_write_configs_includes_mod_binds(self):
        from quake_installer import binds_mods
        tmp = tempfile.mkdtemp()
        try:
            o = Options(tmp, "Ranger", "soft", binds={},
                        mod_binds={"arena": {"stats": "i", "break": "b"}})
            # Pretend gamedirs exist for client_dirs targets
            for label, target in __import__("quake_installer.mods", fromlist=["mods"]).client_dirs(
                    {"key": "arena", "gamedir": "arena", "clients": ["fte", "unez"], "title": "Arena"},
                    o.fte_dir, o.unez_dir):
                os.makedirs(target, exist_ok=True)
            r = Result()
            rep = Reporter()
            rep.log = lambda m: None
            write_configs(o, rep, r)
            for client in ("FTE", "unezQuake"):
                base = o.fte_dir if client == "FTE" else o.unez_dir
                bp = os.path.join(base, "arena", "binds.cfg")
                self.assertTrue(os.path.isfile(bp), bp)
                with open(bp) as fh:
                    body = fh.read()
                self.assertIn('bind i "impulse 68"', body)
                self.assertIn('bind b "impulse 70"', body)
                with open(os.path.join(base, "arena", "autoexec.cfg")) as fh:
                    self.assertIn("exec binds.cfg", fh.read())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



# Point QUAKE_RESOURCE1 at resource.1 from quake106.zip to run the LH5 decoder test.
RES1 = os.environ.get("QUAKE_RESOURCE1", os.path.join(os.path.dirname(__file__), "data", "resource.1"))


@unittest.skipUnless(os.path.isfile(RES1), "resource.1 not available")
class LhaTests(unittest.TestCase):
    def test_extract_pak0_builtin(self):
        out = os.path.join(tempfile.mkdtemp(), "pak0.pak")
        name = lha.extract_member(RES1, "ID1/PAK0.PAK", out)
        self.assertEqual(name.upper(), "ID1/PAK0.PAK")
        self.assertTrue(extract.pak0_is_valid(out))


if __name__ == "__main__":
    unittest.main()
