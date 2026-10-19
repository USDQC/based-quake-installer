"""Quick-use aliases (PainKeep, Thunderwalker CTF)."""
import unittest

from quake_installer import binds_mods, cfg


class QuickAliasTests(unittest.TestCase):
    def test_painkeep_airfist_text(self):
        t = binds_mods.render_mod_binds_cfg("painkeep", {"q_airfist": "f"})
        self.assertIn('alias +bqi_airfist "impulse 30; +attack"', t)
        self.assertIn('alias -bqi_airfist "-attack; impulse 69"', t)
        self.assertIn("bind f +bqi_airfist", t)
        # aliases are defined before the bind that uses them
        self.assertLess(t.index("alias +bqi_airfist"), t.index("bind f"))

    def test_painkeep_items(self):
        want = {"q_gravitywell": "33", "q_beartrap": "34", "q_autosentry": "35", "q_beans": "36"}
        for action, imp in want.items():
            t = binds_mods.render_mod_binds_cfg("painkeep", {action: "g"})
            name = binds_mods.QUICK_ALIASES["painkeep"][action][0]
            self.assertIn('alias +%s "impulse %s; +attack"' % (name, imp), t)
            self.assertIn('alias -%s "-attack; impulse 69"' % name, t)
            self.assertIn("bind g +%s" % name, t)

    def test_thunderwalker_text(self):
        t = binds_mods.render_mod_binds_cfg("thunderwalker", {"q_airfist": "f", "q_hook": "MOUSE2"})
        lines = t.split("\r\n")
        for want in ('alias +bqi_airfist "impulse 47; +attack"',
                     'alias -bqi_airfist "-attack; impulse 69"',
                     'alias +bqi_hook "impulse 22; +attack"',
                     'alias -bqi_hook "-attack; impulse 69"',
                     "bind f +bqi_airfist", "bind MOUSE2 +bqi_hook"):
            self.assertIn(want, lines)

    def test_no_alias_lines_when_unused(self):
        t = binds_mods.render_mod_binds_cfg("painkeep", {"lastweapon": "q"})
        self.assertNotIn("alias", t)
        self.assertIn('bind q "impulse 69"', t)
        self.assertNotIn("alias", binds_mods.render_mod_binds_cfg("painkeep", {}))

    def test_shared_key_keeps_first_only(self):
        t = binds_mods.render_mod_binds_cfg("painkeep", {"q_airfist": "f", "q_beans": "F"})
        self.assertIn("+bqi_airfist", t)
        self.assertNotIn("bqi_beans", t)

    def test_rows_and_aliases_match(self):
        self.assertEqual(set(binds_mods.QUICK_ALIASES), {"painkeep", "thunderwalker"})
        for mod_key in binds_mods.mods_with_bind_ui():
            quick = {a for a, cmd, _l in binds_mods.actions_for(mod_key) if cmd.startswith("+bqi_")}
            self.assertEqual(quick, set(binds_mods.QUICK_ALIASES.get(mod_key, {})), mod_key)
            for a, cmd, _l in binds_mods.actions_for(mod_key):
                if a in quick:
                    self.assertEqual(cmd, "+" + binds_mods.QUICK_ALIASES[mod_key][a][0])

    def test_alias_text_is_safe(self):
        for mod_key, table in binds_mods.QUICK_ALIASES.items():
            names = [n for n, _s in table.values()]
            self.assertEqual(len(names), len(set(names)))
            for action in table:
                for line in binds_mods.quick_alias_lines(mod_key, action):
                    self.assertEqual(line.count('"'), 2)
                    self.assertRegex(line, r'^alias [+-]bqi_[a-z]+ "[a-z0-9 ;+-]+"$')

    def test_quick_rows_default_blank_and_conflicts(self):
        # Nothing preset; a clash with a general bind is reported, not silent.
        self.assertEqual(binds_mods.key_conflicts("thunderwalker", {}, cfg.PRESET_VANILLA), [])
        conf = binds_mods.key_conflicts("thunderwalker", {"q_hook": "CTRL"}, cfg.PRESET_VANILLA)
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0][0], "CTRL")

    def test_capture_keys_work(self):
        # Keys from click-to-capture boxes (mouse, keypad) render as plain binds.
        t = binds_mods.render_mod_binds_cfg("thunderwalker", {"q_hook": "MOUSE4", "q_airfist": "KP_INS"})
        self.assertIn("bind MOUSE4 +bqi_hook", t)
        self.assertIn("bind KP_INS +bqi_airfist", t)


if __name__ == "__main__":
    unittest.main()
