import unittest

from quake_installer import gui


class ThemeNames(unittest.TestCase):
    def test_picker_says_light_and_dark(self):
        self.assertEqual([label for _k, label in gui.THEMES], ["Light", "Dark"])
        self.assertNotIn("Classic", [label for _k, label in gui.THEMES])

    def test_old_saved_values_load_as_light(self):
        for old in ("classic", "Classic", "light", "sv-light", "sun-valley-light"):
            self.assertEqual(gui.THEME_ALIASES.get(old.lower()), "classic", old)
        self.assertEqual(dict(gui.THEMES)["classic"], "Light")

    def test_dark_unchanged(self):
        self.assertEqual(gui.THEME_ALIASES["sv-dark"], "sv-dark")


if __name__ == "__main__":
    unittest.main()
