"""Folder hint under the install-mode row (pure formatter, no Tk root)."""

import os
import unittest

from quake_installer.constants import FTE_DIRNAME, UNEZ_DIRNAME
from quake_installer.gui import paths_hint


class PathsHintTests(unittest.TestCase):
    def test_full_install_defaults(self):
        root = os.path.join("C:", "Games")
        self.assertEqual(paths_hint(False, root),
                         "Creates:  %s   and   %s"
                         % (os.path.join(root, UNEZ_DIRNAME),
                            os.path.join(root, FTE_DIRNAME)))

    def test_full_install_custom_targets_and_one_engine(self):
        self.assertEqual(
            paths_hint(False, "C:/Games", install_fte=False,
                       unez_target="D:/ezquake"),
            "Creates:  " + os.path.normpath("D:/ezquake"))
        self.assertEqual(
            paths_hint(False, "C:/Games", install_unez=False,
                       fte_target="E:/FTE"),
            "Creates:  " + os.path.normpath("E:/FTE"))

    def test_full_install_cleans_quotes_and_spaces(self):
        self.assertEqual(
            paths_hint(False, '  "C:/Games"  ', unez_target=' "D:/ez quake" '),
            "Creates:  %s   and   %s"
            % (os.path.normpath("D:/ez quake"),
               os.path.join(os.path.normpath("C:/Games"), FTE_DIRNAME)))

    def test_no_engine_selected(self):
        self.assertEqual(paths_hint(False, "C:/Games", False, False),
                         "No engine selected - open Settings.")

    def test_mods_only_folders(self):
        self.assertEqual(
            paths_hint(True, "ignored", unez_path="C:/ezquake", fte_path="D:/FTE"),
            "Mods go into: %s and %s" % (os.path.normpath("C:/ezquake"),
                                         os.path.normpath("D:/FTE")))
        self.assertEqual(paths_hint(True, "ignored", unez_path=" "),
                         "Choose the unezQuake and/or FTE folder you already have.")


if __name__ == "__main__":
    unittest.main()
