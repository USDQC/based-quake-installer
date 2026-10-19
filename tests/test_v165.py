"""v1.6.5: click-then-press bind capture, per-box clear, Show scoreboard bind."""

import re
import unittest

from quake_installer import binds_mods, cfg, keycapture



class KeysymMappingTests(unittest.TestCase):
    def k(self, keysym, keycode=None, ws="x11"):
        return keycapture.key_from_keysym(keysym, keycode, ws)

    def test_letters_digits(self):
        self.assertEqual(self.k("a"), "a")
        self.assertEqual(self.k("A"), "a")  # shift held
        self.assertEqual(self.k("z"), "z")
        self.assertEqual(self.k("7"), "7")

    def test_named_keys(self):
        cases = {
            "space": "SPACE", "Tab": "TAB", "ISO_Left_Tab": "TAB", "Return": "ENTER",
            "BackSpace": "BACKSPACE", "Shift_L": "SHIFT", "Shift_R": "SHIFT",
            "Control_L": "CTRL", "Control_R": "CTRL", "Alt_L": "ALT", "Alt_R": "ALT",
            "Up": "UPARROW", "Down": "DOWNARROW", "Left": "LEFTARROW", "Right": "RIGHTARROW",
            "Insert": "INS", "Delete": "DEL", "Home": "HOME", "End": "END",
            "Prior": "PGUP", "Next": "PGDN", "Pause": "PAUSE", "Caps_Lock": "CAPSLOCK",
            "F1": "F1", "F12": "F12",
        }
        for ks, want in cases.items():
            self.assertEqual(self.k(ks), want, ks)

    def test_keypad(self):
        cases = {
            "KP_Enter": "KP_ENTER", "KP_Home": "KP_HOME", "KP_7": "KP_HOME",
            "KP_Up": "KP_UPARROW", "KP_8": "KP_UPARROW", "KP_Begin": "KP_5", "KP_5": "KP_5",
            "KP_Insert": "KP_INS", "KP_0": "KP_INS", "KP_Delete": "KP_DEL",
            "KP_Decimal": "KP_DEL", "KP_Divide": "KP_SLASH", "KP_Multiply": "KP_STAR",
            "KP_Subtract": "KP_MINUS", "KP_Add": "KP_PLUS", "KP_Next": "KP_PGDN",
        }
        for ks, want in cases.items():
            self.assertEqual(self.k(ks), want, ks)

    def test_semicolon_and_punctuation(self):
        self.assertEqual(self.k("semicolon"), "SEMICOLON")
        self.assertEqual(self.k("colon"), "SEMICOLON")
        for ks, want in {"comma": ",", "period": ".", "slash": "/", "backslash": "\\",
                         "bracketleft": "[", "bracketright": "]", "apostrophe": "'",
                         "grave": "`", "asciitilde": "`", "minus": "-", "equal": "=",
                         "plus": "=", "question": "/", "exclam": "1"}.items():
            self.assertEqual(self.k(ks), want, ks)
        t = cfg.render_autoexec(cfg.CLIENT_FTE, "p", {"jump": self.k("semicolon")}, "soft")
        self.assertIn("bind SEMICOLON +jump", t)
        self.assertNotIn("bind ; ", t)

    def test_escape_and_unknown_are_not_keys(self):
        self.assertIsNone(self.k("Escape"))
        self.assertEqual(keycapture.CANCEL, "Escape")
        self.assertIsNone(self.k("odiaeresis"))
        self.assertIsNone(self.k("Super_L"))
        self.assertIsNone(self.k(""))

    def test_windows_vk_fallback(self):
        self.assertEqual(self.k("odiaeresis", 186, "win32"), "SEMICOLON")
        self.assertEqual(self.k("??", 65, "win32"), "a")
        self.assertIsNone(self.k("odiaeresis", 186, "x11"))

    def test_mouse_buttons(self):
        b = keycapture.key_from_button
        self.assertEqual([b(i, "x11") for i in (1, 3, 2, 8, 9, 4, 5)],
                         ["MOUSE1", "MOUSE2", "MOUSE3", "MOUSE4", "MOUSE5",
                          "MWHEELUP", "MWHEELDOWN"])
        self.assertEqual([b(i, "win32") for i in (1, 3, 2, 4, 5, 8, 9)],
                         ["MOUSE1", "MOUSE2", "MOUSE3", "MOUSE4", "MOUSE5", "MOUSE4", "MOUSE5"])
        self.assertEqual(b(2, "aqua"), "MOUSE2")
        self.assertIsNone(b(6, "x11"))
        self.assertEqual(keycapture.key_from_wheel(120), "MWHEELUP")
        self.assertEqual(keycapture.key_from_wheel(-120), "MWHEELDOWN")
        self.assertIsNone(keycapture.key_from_wheel(0))

    def test_every_name_is_valid_for_both_engines(self):
        # Every produced name is canonical for cfg.normalize_key and is in both the
        # ezQuake (unezQuake) and FTE key tables (or is a single printable key).
        both = set(x.upper() for x in ENGINE_KEYNAMES)
        for name in keycapture.all_names():
            self.assertEqual(cfg.normalize_key(name), name, name)
            if len(name) > 1:
                self.assertIn(name.upper(), both, name)


# Key names present in BOTH ezQuake keys.c and FTE keys.c (checked against upstream).
ENGINE_KEYNAMES = """TAB ENTER ESCAPE SPACE BACKSPACE UPARROW DOWNARROW LEFTARROW RIGHTARROW
ALT CTRL SHIFT F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 INS DEL PGDN PGUP HOME END
KP_HOME KP_UPARROW KP_PGUP KP_LEFTARROW KP_5 KP_RIGHTARROW KP_END KP_DOWNARROW KP_PGDN
KP_ENTER KP_INS KP_DEL KP_SLASH KP_MINUS KP_PLUS KP_STAR KP_MULTIPLY MOUSE1 MOUSE2 MOUSE3
MOUSE4 MOUSE5 MWHEELUP MWHEELDOWN PAUSE CAPSLOCK SEMICOLON""".split()


class ShowScoresTests(unittest.TestCase):
    def test_action_and_default(self):
        self.assertEqual(cfg.ACTION_BY_ID["showscores"][1], "+showscores")
        self.assertEqual(cfg.PRESET_VANILLA["showscores"], "TAB")

    def test_written_for_both_clients(self):
        for client in (cfg.CLIENT_FTE, cfg.CLIENT_UNEZ):
            t = cfg.render_autoexec(client, "p", cfg.PRESET_VANILLA, "soft")
            lines = t.split("\r\n")
            self.assertIn("bind TAB +showscores", lines, client)
            self.assertLess(lines.index("unbindall"), lines.index("bind TAB +showscores"))

    def test_blank_leaves_tab_unbound(self):
        b = dict(cfg.PRESET_VANILLA)
        b["showscores"] = ""
        t = cfg.render_autoexec(cfg.CLIENT_FTE, "p", b, "soft")
        self.assertNotIn("+showscores", t)
        self.assertFalse(re.search(r"(?mi)^bind tab ", t))

    def test_mod_conflict_is_reported_and_stays_in_mod_binds_cfg(self):
        mod = {"inv": "TAB"}
        conf = binds_mods.key_conflicts("fortress", mod, cfg.PRESET_VANILLA)
        self.assertEqual(conf, [("TAB", "Inventory", "Show scoreboard")])
        self.assertIn("bind TAB inv", binds_mods.render_mod_binds_cfg("fortress", mod))
        # general autoexec is unchanged
        t = cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", cfg.PRESET_VANILLA, "soft")
        self.assertIn("bind TAB +showscores", t)
        self.assertNotIn("inv", t.split("unbindall")[1].split("viewsize")[0])
        self.assertEqual(binds_mods.key_conflicts("fortress", {"inv": "i"},
                                                  cfg.PRESET_VANILLA), [])

    def test_no_mod_action_defaults_to_tab(self):
        for mod_key in binds_mods.mods_with_bind_ui():
            for action_id, cmd, _label in binds_mods.actions_for(mod_key):
                self.assertNotIn("showscores", cmd)


if __name__ == "__main__":
    unittest.main()
