"""Folder hint under the install-mode row (pure formatter, no Tk root)."""

import os
import unittest

from quake_installer.constants import FTE_DIRNAME, UNEZ_DIRNAME
from quake_installer.gui import paths_hint


class PathsHintTests(unittest.TestCase):
    def _new(self, _path):
        return False

    def _only(self, *existing):
        names = {os.path.normcase(os.path.normpath(p)) for p in existing}
        return lambda p: os.path.normcase(os.path.normpath(p)) in names

    def test_full_install_defaults_are_new(self):
        root = os.path.join("C:", "Games")
        self.assertEqual(
            paths_hint(False, root, exists=self._new),
            "Installs to: %s (new) and %s (new)"
            % (os.path.join(root, UNEZ_DIRNAME), os.path.join(root, FTE_DIRNAME)))

    def test_full_install_marks_existing_folders(self):
        self.assertEqual(
            paths_hint(False, "C:/Games", unez_target="D:/ezquake",
                       fte_target="E:/FTE", exists=self._only("D:/ezquake")),
            "Installs to: %s (existing) and %s (new)"
            % (os.path.normpath("D:/ezquake"), os.path.normpath("E:/FTE")))

    def test_full_install_custom_targets_and_one_engine(self):
        self.assertEqual(
            paths_hint(False, "C:/Games", install_fte=False,
                       unez_target="D:/ezquake", exists=self._new),
            "Installs to: %s (new)" % os.path.normpath("D:/ezquake"))
        self.assertEqual(
            paths_hint(False, "C:/Games", install_unez=False,
                       fte_target="E:/FTE", exists=self._new),
            "Installs to: %s (new)" % os.path.normpath("E:/FTE"))

    def test_full_install_cleans_quotes_and_spaces(self):
        self.assertEqual(
            paths_hint(False, '  "C:/Games"  ', unez_target=' "D:/ez quake" ',
                       exists=self._new),
            "Installs to: %s (new) and %s (new)"
            % (os.path.normpath("D:/ez quake"),
               os.path.join(os.path.normpath("C:/Games"), FTE_DIRNAME)))

    def test_no_engine_selected(self):
        self.assertEqual(paths_hint(False, "C:/Games", False, False, exists=self._new),
                         "No engine is turned on. Open Settings to choose one.")

    def test_mods_only_folders_with_markers(self):
        self.assertEqual(
            paths_hint(True, "ignored", unez_path="C:/ezquake", fte_path="D:/FTE",
                       exists=self._only("C:/ezquake")),
            "Mods go into: %s (existing) and %s (new)"
            % (os.path.normpath("C:/ezquake"), os.path.normpath("D:/FTE")))
        self.assertEqual(
            paths_hint(True, "ignored", unez_path=" ", exists=self._new),
            "Choose the unezQuake and/or FTE folder you already have.")


if __name__ == "__main__":
    unittest.main()
