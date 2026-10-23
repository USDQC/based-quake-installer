"""Mods only (existing clients): fake unezQuake / FTE trees, FTE home dir
detection, user cfgs kept, no client download, server switch into a mod."""
import hashlib, io, os, shutil, tempfile, unittest, zipfile
from unittest import mock

from quake_installer import (binds_mods, clients, download, existing, installer, manifest,
                             mods as modlib, updater)


def _zip(gamedir, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, data in files.items():
            zf.writestr(gamedir + "/" + n, data)
    return buf.getvalue()


def _pak(names):
    """Minimal Quake PACK containing the given file names (empty files)."""
    import struct
    dirents = b"".join(struct.pack("<56sii", n.encode(), 12, 0) for n in names)
    return struct.pack("<4sii", b"PACK", 12, len(dirents)) + dirents


def _w(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        fh.write(text)


def _r(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


class Rep(object):
    def __init__(self): self.lines = []
    def log(self, m): self.lines.append(m)
    def step(self, *a): self.lines.append("step %r" % (a,))
    def progress(self, *a): pass


def _no_net(*a, **k):
    raise AssertionError("mods-only must not download clients")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.unez = os.path.join(self.t, "MyEzQuake")
        self.fte = os.path.join(self.t, "MyFTE")
        _w(os.path.join(self.unez, "unezquake"), "bin")
        _w(os.path.join(self.unez, "id1", "pak0.pak"), "pak")
        _w(os.path.join(self.unez, "qw", "skins", "base.pcx"), "skin")
        _w(os.path.join(self.fte, "fteqw64"), "bin")
        _w(os.path.join(self.fte, "id1", "pak0.pak"), "pak")
        # the user's own cfgs (must survive)
        _w(os.path.join(self.unez, "id1", "autoexec.cfg"), "bind x +jump\n")
        _w(os.path.join(self.unez, "ezquake", "configs", "config.cfg"), "name me\n")
        _w(os.path.join(self.fte, "fte.cfg"), "seta name me\n")
        self.zdir = os.path.join(self.t, "zips")
        os.makedirs(self.zdir)
        pk = {"pak0.pak": _pak(["quake.rc", "default.cfg", "maps/start.bsp"]),
              "progs.dat": "p", "qwprogs.dat": "q", "server.cfg": "map start\n",
              "default.cfg": "// mod default\n"}
        ctf = {"qwprogs.dat": "q", "pak0.pak": _pak(["maps/e1m1.bsp"])}
        aq = {"pak0.pak": _pak(["maps/aq.bsp"]), "AUTOEXEC.CFG": "bind a +attack\n"}
        skins = {"skins/blue.pcx": "s"}
        sprays = {"sprays/tag.png": "s"}
        self.specs = [
            self._spec("painkeep", "painkeep", ["fte", "unez"], pk),
            self._spec("thunderwalker", "ctf", ["fte", "unez"], ctf),
            self._spec("airquake", "airquake", ["fte"], aq),
            self._spec("skins", "qw", ["fte", "unez"], skins, pack="skins"),
            self._spec("sprays", "qw", ["unez"], sprays, pack="sprays"),
        ]
        self.files = {s["key"]: os.path.join(self.zdir, s["key"] + ".zip") for s in self.specs}

    def _spec(self, key, gamedir, cl, files, pack=None):
        data = _zip(gamedir, files)
        p = os.path.join(self.zdir, key + ".zip")
        with open(p, "wb") as fh:
            fh.write(data)
        s = {"key": key, "gamedir": gamedir, "clients": cl, "title": key.title(),
             "version": "1", "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
             "file": key + ".zip", "url": "PASTE"}
        if pack:
            s.update({"kind": "pack", "subdir": pack})
        return s

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def opts(self, unez=True, fte=True, cfg_dir=None, **kw):
        return installer.Options(
            self.unez if unez else self.fte, "Ranger", "soft",
            binds={"jump": "SPACE"}, mod_binds={"thunderwalker": {"q_airfist": "f"}},
            mod_files=self.files, existing=True, unez_path=self.unez if unez else None,
            fte_path=self.fte if fte else None, fte_cfg_dir=cfg_dir, platform="linux", **kw)

    def run_existing(self, o):
        with mock.patch.object(modlib, "load_specs", lambda *a, **k: list(self.specs)), \
                mock.patch.object(modlib, "load_specs_online",
                                  lambda *a, **k: (list(self.specs), None)), \
                mock.patch.object(clients, "resolve_unez", _no_net), \
                mock.patch.object(clients, "resolve_fte", _no_net), \
                mock.patch.object(clients, "install_unez", _no_net), \
                mock.patch.object(clients, "install_fte", _no_net), \
                mock.patch.object(download, "download", _no_net), \
                mock.patch.object(download, "download_first", _no_net):
            return installer.run_install(o, Rep())


class ModsOnlyTests(Fixture):
    def test_installs_into_both_and_leaves_clients(self):
        res = self.run_existing(self.opts())
        self.assertEqual(res.mods_failed, [])
        for d in (self.unez, self.fte):
            self.assertTrue(os.path.isfile(os.path.join(d, "painkeep", "pak0.pak")))
            self.assertTrue(os.path.isfile(os.path.join(d, "qw", "skins", "blue.pcx")))
            self.assertTrue(os.path.isfile(os.path.join(d, "id1", "based.cfg")))
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "qw", "sprays", "tag.png")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "qw", "sprays")))
        self.assertFalse(os.path.exists(os.path.join(self.unez, "airquake")))
        # no default.fmf, binaries untouched, the user's skin kept
        self.assertFalse(os.path.exists(os.path.join(self.fte, "default.fmf")))
        self.assertEqual(_r(os.path.join(self.fte, "fteqw64")), "bin")
        self.assertEqual(_r(os.path.join(self.unez, "unezquake")), "bin")
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "qw", "skins", "base.pcx")))
        # no UnezQuake/ FTE/ subfolders created
        self.assertFalse(os.path.isdir(os.path.join(self.unez, "FTE")))
        self.assertFalse(os.path.isdir(os.path.join(self.unez, "unezQuake")))
        self.assertTrue(os.path.isfile(manifest.path_for(self.unez)))

    def test_user_cfgs_not_overwritten(self):
        _w(os.path.join(self.unez, "painkeep", "DEFAULT.CFG"), "// my pk tweaks\n")
        _w(os.path.join(self.fte, "painkeep", "default.cfg"), "// my fte pk tweaks\n")
        _w(os.path.join(self.unez, "ctf", "frontend.cfg"), "echo mine\n")
        self.run_existing(self.opts())
        self.assertIn("my pk tweaks", _r(os.path.join(self.unez, "painkeep", "default.cfg")))
        self.assertIn("my fte pk tweaks", _r(os.path.join(self.fte, "painkeep", "default.cfg")))
        ua = _r(os.path.join(self.unez, "id1", "autoexec.cfg"))
        self.assertTrue(ua.startswith("bind x +jump"))
        self.assertEqual(ua.lower().count("exec based.cfg"), 1)
        fe = _r(os.path.join(self.unez, "ctf", "frontend.cfg"))
        self.assertTrue(fe.startswith("echo mine"))
        self.assertIn("exec autoexec.cfg", fe)
        self.assertEqual(_r(os.path.join(self.unez, "ezquake", "configs", "config.cfg")),
                         "name me\n")
        self.assertEqual(_r(os.path.join(self.fte, "fte.cfg")), "seta name me\n")
        # AirQuake's own AUTOEXEC.CFG content is kept in the merged autoexec
        self.assertIn("bind a +attack", _r(os.path.join(self.fte, "airquake", "autoexec.cfg")))
        # re-run is idempotent
        self.run_existing(self.opts())
        self.assertEqual(_r(os.path.join(self.unez, "id1", "autoexec.cfg")).lower()
                         .count("exec based.cfg"), 1)

    def test_skip_fte(self):
        res = self.run_existing(self.opts(fte=False))
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "ctf", "binds.cfg")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "ctf")))
        self.assertEqual(res.mods_failed, [])

    def test_skip_unez(self):
        self.run_existing(self.opts(unez=False))
        self.assertTrue(os.path.isfile(os.path.join(self.fte, "ctf", "quake.rc")))
        self.assertFalse(os.path.exists(os.path.join(self.unez, "ctf")))
        self.assertTrue(os.path.isfile(manifest.path_for(self.fte)))

    def test_neither_is_error(self):
        o = self.opts()
        o.unez_path = o.fte_path = None
        with self.assertRaises(installer.InstallError):
            installer.run_install(o, Rep())

    def test_uppercase_gamedir_folder_normalized(self):
        if os.name == "nt":
            self.skipTest("case-insensitive FS")
        _w(os.path.join(self.unez, "PainKeep", "PAK1.PAK"), "old")
        self.run_existing(self.opts())
        self.assertEqual(sorted(n for n in os.listdir(self.unez) if n.lower() == "painkeep"),
                         ["painkeep"])
        self.assertTrue(os.path.isfile(os.path.join(self.unez, "painkeep", "pak1.pak")))

    def test_configs_only(self):
        self.run_existing(self.opts())
        o = self.opts(configs_only=True)
        o.binds = {"jump": "j"}
        self.run_existing(o)
        self.assertIn("bind j", _r(os.path.join(self.unez, "id1", "based.cfg")).lower())


class HomeModeInstallTests(Fixture):
    def test_fte_home_mode_cfgs_go_home_data_stays(self):
        home = os.path.join(self.t, "home", ".local", "share", "quake")
        self.run_existing(self.opts(cfg_dir=home))
        self.assertTrue(os.path.isfile(os.path.join(self.fte, "ctf", "qwprogs.dat")))
        self.assertTrue(os.path.isfile(os.path.join(home, "ctf", "binds.cfg")))
        self.assertTrue(os.path.isfile(os.path.join(home, "ctf", "autoexec.cfg")))
        self.assertTrue(os.path.isfile(os.path.join(home, "ctf", "quake.rc")))
        self.assertTrue(os.path.isfile(os.path.join(home, "id1", "based.cfg")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "ctf", "binds.cfg")))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "id1", "based.cfg")))
        # PainKeep's own startup cfgs (pak) are in the install dir: no hook needed
        self.assertEqual(binds_mods._find_ci(os.path.join(home, "painkeep"), "quake.rc"), [])
        # AirQuake's AUTOEXEC.CFG (install dir) is carried into the shadowing home copy
        self.assertIn("bind a +attack", _r(os.path.join(home, "airquake", "autoexec.cfg")))


# ---------------------------------------------------------------- switch simulation
def _resolve(search, name):
    for d in search:
        for n in binds_mods._find_ci(d, name):
            return os.path.join(d, n)
        for n in os.listdir(d) if os.path.isdir(d) else []:
            if n.lower().endswith(".pak") and name in binds_mods._archive_names(os.path.join(d, n)):
                return os.path.join(d, n) + "#" + name
    return None


def _run(search, name, seen=None, depth=0):
    """Follow exec lines like the engine would; returns all executed lines."""
    seen = seen if seen is not None else []
    p = _resolve(search, name)
    if not p or "#" in p or depth > 8:
        return seen
    for line in _r(p).splitlines():
        st = line.strip()
        seen.append(st)
        if st.lower().startswith("exec "):
            _run(search, st.split(None, 1)[1].strip('"'), seen, depth + 1)
    return seen


def fte_switch(install, home, gamedir):
    """FTE FS_ChangeGame: reload configs iff a conffile now resolves elsewhere; then
    exec quake.rc. Home gamedirs are searched before install ones (FS_AddGameDirectory)."""
    def path(g):
        out = []
        for gd in ([g] if g else []) + ["qw", "id1"]:
            if home:
                out.append(os.path.join(home, gd))
            out.append(os.path.join(install, gd))
        return out
    before = {c: _resolve(path(None), c) for c in binds_mods.FTE_RELOAD_TRIGGERS}
    after = {c: _resolve(path(gamedir), c) for c in binds_mods.FTE_RELOAD_TRIGGERS}
    if before == after:
        return []
    return _run(path(gamedir), "quake.rc")


def unez_switch(unez, gamedir):
    """unezQuake: on a gamedir change it execs {gamedir}/frontend.cfg."""
    search = [os.path.join(unez, g) for g in (gamedir, "qw", "id1")]
    if not binds_mods._find_ci(search[0], "frontend.cfg"):
        return []
    return _run(search, "frontend.cfg")


class ServerSwitchTests(Fixture):
    def test_switch_into_ctf_loads_binds_both_clients(self):
        self.run_existing(self.opts())
        self.assertIn("bind f +bqi_airfist", unez_switch(self.unez, "ctf"))
        self.assertIn("bind f +bqi_airfist", fte_switch(self.fte, None, "ctf"))

    def test_switch_into_ctf_fte_home_mode(self):
        home = os.path.join(self.t, "fhome")
        self.run_existing(self.opts(cfg_dir=home))
        lines = fte_switch(self.fte, home, "ctf")
        self.assertIn("bind f +bqi_airfist", lines)
        self.assertIn("exec based.cfg", [l.lower() for l in lines])

    def test_painkeep_startup_runs_both_clients(self):
        self.run_existing(self.opts())
        # FTE: PainKeep's pak ships quake.rc/default.cfg -> reload triggers, our
        # autoexec chain is reached via the pak's quake.rc (not simulated) so just
        # check the trigger is the mod's and our quake.rc was not added.
        pk = os.path.join(self.fte, "painkeep")
        self.assertTrue(binds_mods.mod_has_fte_reload_trigger(pk))
        self.assertEqual(binds_mods._find_ci(pk, "quake.rc"), [])
        self.assertIn("exec binds.cfg", _r(os.path.join(pk, "autoexec.cfg")))
        # unezQuake: frontend.cfg -> autoexec.cfg -> based.cfg + binds.cfg
        lines = [l.lower() for l in unez_switch(self.unez, "painkeep")]
        self.assertIn("exec based.cfg", lines)
        self.assertIn("exec binds.cfg", lines)
        # files lowercase so Linux engines find pak0.pak/server.cfg
        self.assertEqual(sorted(os.listdir(pk)), sorted(n.lower() for n in os.listdir(pk)))


class FteHomeDetectTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.fte = os.path.join(self.t, "fte")
        os.makedirs(os.path.join(self.fte, "id1"))
        self.home = os.path.join(self.t, "h")
        os.makedirs(self.home)
        self.env = {"HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def fmf(self, text):
        _w(os.path.join(self.fte, "default.fmf"), text)

    def det(self, **kw):
        return existing.detect_fte_config(self.fte, env=self.env, platform="linux", **kw)

    def test_disablehomedir_means_install(self):
        self.fmf("FTEManifestVer 1\ngame afterquake\ndisablehomedir 1\n")
        os.makedirs(os.path.join(self.home, ".local", "share", "afterquake"))
        d = self.det()
        self.assertEqual(d.mode, existing.MODE_INSTALL)
        self.assertEqual(d.write_root, self.fte)

    def test_disablehomedir_0_forces_home(self):
        self.fmf("game afterquake\ndisablehomedir 0\n")
        d = self.det()
        self.assertEqual(d.mode, existing.MODE_HOME)
        self.assertEqual(d.write_root, os.path.join(self.home, ".local", "share", "afterquake"))

    def test_auto_uses_existing_xdg_home(self):
        self.fmf("game afterquake\n")
        h = os.path.join(self.home, ".local", "share", "afterquake")
        os.makedirs(h)
        self.assertEqual(self.det().write_root, h)

    def test_auto_no_home_writable_install(self):
        self.fmf("game afterquake\nhomedirmode auto\n")
        self.assertEqual(self.det().mode, existing.MODE_INSTALL)

    def test_auto_readonly_install_uses_home(self):
        self.fmf("game afterquake\n")
        d = self.det(writable=False)
        self.assertEqual(d.mode, existing.MODE_HOME)

    def test_legacy_dot_home(self):
        self.fmf("game afterquake\n")
        os.makedirs(os.path.join(self.home, ".afterquake"))
        self.assertEqual(self.det().write_root, os.path.join(self.home, ".afterquake"))

    def test_xdg_data_home_and_ftehome(self):
        self.fmf("game quake\n")
        x = os.path.join(self.t, "xdg")
        os.makedirs(os.path.join(x, "quake"))
        self.env["XDG_DATA_HOME"] = x
        self.assertEqual(self.det().write_root, os.path.join(x, "quake"))
        self.env["FTEHOME"] = os.path.join(self.t, "fh")
        self.assertEqual(self.det().write_root, os.path.join(self.t, "fh"))

    def test_no_fmf_with_home_is_ambiguous(self):
        os.makedirs(os.path.join(self.home, ".local", "share", "quake"))
        d = self.det()
        self.assertEqual(d.mode, existing.MODE_ASK)
        self.assertIsNone(d.write_root)

    def test_no_fmf_no_home_is_install(self):
        self.assertEqual(self.det().mode, existing.MODE_INSTALL)

    def test_describe_wording(self):
        # No cfg is needed: the folder layout alone decides.
        self.fmf("game afterquake\nhomedirmode auto\n")
        self.assertEqual(self.det().describe(),
                         "FTE configs: %s  (install folder; no FTE home folder found)"
                         % self.fte)
        home = os.path.join(self.home, ".local", "share", "afterquake")
        os.makedirs(home)
        self.assertEqual(self.det().describe(),
                         "FTE configs: %s  (home folder; found automatically)" % home)
        self.fmf("game afterquake\ndisablehomedir 1\n")
        self.assertIn("(install folder; disabled by default.fmf)",
                      self.det().describe())
        os.remove(os.path.join(self.fte, "default.fmf"))
        os.makedirs(os.path.join(self.home, ".local", "share", "quake"))
        self.assertIn("needs a choice", self.det().describe())

    def test_windows_candidates(self):
        env = {"LOCALAPPDATA": os.path.join(self.t, "lad"),
               "USERPROFILE": os.path.join(self.t, "prof")}
        self.fmf("game afterquake\nname \"AfterQuake\"\n")
        os.makedirs(os.path.join(self.t, "prof", "Saved Games", "afterquake"))
        d = existing.detect_fte_config(self.fte, env=env, platform="windows")
        self.assertEqual(d.mode, existing.MODE_HOME)
        self.assertEqual(os.path.normcase(d.write_root),
                         os.path.normcase(os.path.join(self.t, "prof", "Saved Games",
                                                       "afterquake")))


class FolderCheckTests(Fixture):
    def test_checks(self):
        self.assertEqual(existing.check_unez_folder(self.unez), [])
        self.assertEqual(existing.check_fte_folder(self.fte), [])
        self.assertTrue(existing.check_unez_folder(self.fte))
        self.assertTrue(existing.check_fte_folder(self.unez))
        self.assertTrue(existing.check_fte_folder(os.path.join(self.t, "nope")))


class UpdateTests(Fixture):
    def test_check_and_apply_mods_only(self):
        self.run_existing(self.opts())
        o = self.opts()
        newer = [dict(s, version="2") for s in self.specs]
        items = updater.check_updates(o.root, "linux", specs=newer, log=lambda m: None,
                                      resolve_unez=_no_net, resolve_fte=_no_net, opts=o)
        comps = {i.component for i in items}
        self.assertFalse(any(c.startswith("client:") for c in comps))
        self.assertTrue(all(i.needs_update for i in items))
        files = self.files

        def local_install(spec, *a, **k):
            k["local_file"] = files[spec["key"]]
            return ORIG_INSTALL(dict(spec, version="1"), *a, **k)
        with mock.patch.object(download, "download", _no_net), \
                mock.patch.object(modlib, "install_mod", local_install):
            up, failed = updater.apply_updates(o, items, Rep())
        self.assertEqual(failed, [])
        self.assertFalse(os.path.exists(os.path.join(self.fte, "default.fmf")))
        self.assertTrue(os.path.isfile(os.path.join(self.fte, "ctf", "quake.rc")))


ORIG_INSTALL = modlib.install_mod

if __name__ == "__main__":
    unittest.main()
