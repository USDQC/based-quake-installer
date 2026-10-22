"""Settings file: new keys round-trip and old files keep loading."""

import json
import os
import shutil
import tempfile
import unittest

from quake_installer import settings


class SettingsFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_old_file_still_loads(self):
        with open(settings.settings_path(self.tmp), "w", encoding="utf-8") as fh:
            json.dump({"root": r"C:\Games", "player_name": "Ranger",
                       "theme": "classic"}, fh)
        data = settings.load(self.tmp)
        self.assertEqual(data["root"], r"C:\Games")
        self.assertEqual(data["player_name"], "Ranger")
        # Not stored yet: the GUI applies "both engines, remember on" defaults.
        self.assertNotIn("install_unez", data)
        self.assertNotIn("remember_dirs", data)

    def test_engine_and_folder_keys_roundtrip(self):
        values = {
            "install_unez": False,
            "install_fte": True,
            "remember_dirs": False,
            "unez_install_path": r"D:\Games\ezquake",
            "fte_install_path": r"E:\Lan\FTE",
        }
        settings.save(values, self.tmp)
        data = settings.load(self.tmp)
        self.assertEqual(data, values)

    def test_update_keeps_existing_values(self):
        settings.save({"root": r"C:\Games", "install_unez": True}, self.tmp)
        settings.update(self.tmp, install_fte=False, remember_dirs=False)
        data = settings.load(self.tmp)
        self.assertEqual(data["root"], r"C:\Games")
        self.assertTrue(data["install_unez"])
        self.assertFalse(data["install_fte"])
        self.assertFalse(data["remember_dirs"])


if __name__ == "__main__":
    unittest.main()
