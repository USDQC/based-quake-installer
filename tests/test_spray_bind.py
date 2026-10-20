"""Spray bind: unezQuake only."""
import unittest

from quake_installer import cfg


class SprayBindTests(unittest.TestCase):
    def test_action(self):
        self.assertEqual(cfg.ACTION_BY_ID["spray"], ("spray", "+spray", "Spray (unezQuake only)"))
        self.assertIn("spray", cfg.UNEZ_ONLY_ACTIONS)

    def test_unez_only(self):
        b = dict(cfg.PRESET_VANILLA, spray="g")
        u = cfg.render_autoexec(cfg.CLIENT_UNEZ, "Ranger", b, "soft")
        f = cfg.render_autoexec(cfg.CLIENT_FTE, "Ranger", b, "soft")
        self.assertIn("bind g +spray", u)
        self.assertNotIn("+spray", f)
        self.assertNotIn("bind g ", f)
        self.assertIn("custom binds (%d actions)" % len(cfg.PRESET_VANILLA), f)

    def test_shared_key_fte_keeps_other_action(self):
        b = {"impulse1": "1", "spray": "1"}
        f = cfg.render_autoexec(cfg.CLIENT_FTE, "Ranger", b, "soft")
        u = cfg.render_autoexec(cfg.CLIENT_UNEZ, "Ranger", b, "soft")
        self.assertIn('bind 1 "impulse 1"', f)
        self.assertIn("bind 1 +spray", u)

    def test_blank_by_default(self):
        for preset in cfg.PRESETS.values():
            self.assertNotIn("spray", preset)
        u = cfg.render_autoexec(cfg.CLIENT_UNEZ, "R", dict(cfg.PRESET_VANILLA), "soft")
        self.assertFalse([l for l in u.splitlines() if l.startswith("bind") and "spray" in l])

    def test_build_binds_default_client_unchanged(self):
        pairs = [p for _t, ps in cfg.build_binds({"spray": "g"}) for p in ps]
        self.assertIn(("g", "+spray"), pairs)


if __name__ == "__main__":
    unittest.main()
