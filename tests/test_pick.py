"""Pick-and-choose clients and mods: selection logic, CLI flags, installer core."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import installer_cli
from quake_installer import installer
from quake_installer.gui import mod_pick_label, mod_pick_state, selected_mod_keys

FTE_ONLY = {"key": "fvf", "title": "Future vs Fantasy", "gamedir": "fvf", "clients": ["fte"]}
UNEZ_ONLY = {"key": "sprays", "title": "Sprays", "gamedir": "qw", "clients": ["unez"]}
BOTH = {"key": "fortress", "title": "Team Fortress", "gamedir": "fortress",
        "clients": ["fte", "unez"]}
SPECS = [FTE_ONLY, UNEZ_ONLY, BOTH]


class SelectionTests(unittest.TestCase):
    def test_labels_name_the_only_client(self):
        self.assertEqual(mod_pick_label(FTE_ONLY), "Future vs Fantasy (FTE only)")
        self.assertEqual(mod_pick_label(UNEZ_ONLY), "Sprays (unezQuake only)")
        self.assertEqual(mod_pick_label(BOTH), "Team Fortress")

    def test_state_follows_clients(self):
        self.assertEqual(mod_pick_state(FTE_ONLY, True, False),
                         (False, "needs FTE"))
        self.assertTrue(mod_pick_state(FTE_ONLY, False, True)[0])
        self.assertTrue(mod_pick_state(BOTH, True, False)[0])
        self.assertFalse(mod_pick_state(BOTH, False, False)[0])

    def test_selected_keys(self):
        all_on = {}
        self.assertEqual(selected_mod_keys(SPECS, all_on, True, True),
                         ["fvf", "sprays", "fortress"])
        # FTE off: the FTE-only mod is dropped even though it is ticked.
        self.assertEqual(selected_mod_keys(SPECS, all_on, True, False),
                         ["sprays", "fortress"])
        self.assertEqual(selected_mod_keys(SPECS, {"fortress": False}, True, True),
                         ["fvf", "sprays"])
        none = {k["key"]: False for k in SPECS}
        self.assertEqual(selected_mod_keys(SPECS, none, True, True), [])


class CliTests(unittest.TestCase):
    def _run(self, *args):
        seen = {}

        def fake(opts, *a, **k):
            seen["opts"] = opts
            raise installer.InstallError("stop")
        with mock.patch.object(installer_cli, "run_install", fake):
            rc = installer_cli.main(["--root", tempfile.gettempdir()] + list(args))
        return rc, seen.get("opts")

    def test_clients_flag(self):
        _rc, o = self._run("--clients", "fte")
        self.assertFalse(o.install_unez)
        self.assertTrue(o.install_fte)
        _rc, o = self._run()
        self.assertTrue(o.install_unez and o.install_fte)

    def test_bad_clients_flag(self):
        with self.assertRaises(SystemExit):
            self._run("--clients", "quakespasm")

    def test_mods_none_and_subset(self):
        _rc, o = self._run("--mods", "none")
        self.assertEqual(o.mods, [])
        self.assertEqual(installer.resolve_mod_keys(o), [])
        _rc, o = self._run("--mods", "fortress")
        self.assertEqual(o.mods, ["fortress"])


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_zero_clients_blocked(self):
        o = installer.Options(self.tmp, "p", "soft", install_unez=False, install_fte=False)
        with self.assertRaises(installer.InstallError):
            installer.run_install(o)

    def test_no_mods_installs_nothing_and_records_nothing(self):
        o = installer.Options(self.tmp, "p", "soft", mods=[], platform="linux")
        rep = installer.Reporter(); rep.log = lambda *a: None
        res = installer.Result()
        man = {"components": {}}
        with mock.patch.object(installer.modlib, "install_mod") as im:
            installer.install_mods(o, rep, res, self.tmp, man=man)
        im.assert_not_called()
        self.assertEqual(man["components"], {})

    def test_fte_only_mod_not_put_in_unez(self):
        o = installer.Options(self.tmp, "p", "soft", mods=["fvf"], install_fte=False,
                              platform="linux")
        rep = installer.Reporter(); rep.log = lambda *a: None
        res = installer.Result()
        with mock.patch.object(installer.modlib, "load_specs_online",
                               return_value=([dict(FTE_ONLY, title="FvF")], None)), \
                mock.patch.object(installer.modlib, "install_mod") as im:
            installer.install_mods(o, rep, res, self.tmp, man={"components": {}})
        im.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "unezQuake", "fvf")))


class SettingsTests(unittest.TestCase):
    def test_mod_picks_round_trip(self):
        from quake_installer import settings
        d = tempfile.mkdtemp()
        try:
            settings.save({"mod_picks": {"grq": False, "fvf": True}}, d)
            self.assertEqual(settings.load(d)["mod_picks"], {"grq": False, "fvf": True})
        finally:
            shutil.rmtree(d, ignore_errors=True)
