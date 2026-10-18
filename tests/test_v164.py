"""v1.6.4: frozen (PyInstaller) paths, --version and --self-test."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from quake_installer import __version__, extract, paths, selftest, settings  # noqa: E402


class FrozenPathTests(unittest.TestCase):
    def test_resource_path_uses_meipass(self):
        with tempfile.TemporaryDirectory() as mei, mock.patch.object(sys, "_MEIPASS", mei, create=True):
            self.assertEqual(paths.resource_path("tools", "7za.exe"), os.path.join(mei, "tools", "7za.exe"))

    def test_exe_side_path_frozen_is_exe_folder(self):
        exe = os.path.join(tempfile.gettempdir(), "Program Files", "BQI", "BasedQuakeInstaller.exe")
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", exe):
            self.assertEqual(paths.exe_side_path("mods.json"), os.path.join(os.path.dirname(exe), "mods.json"))

    def test_bundled_7za_found_in_meipass_on_windows(self):
        with tempfile.TemporaryDirectory() as mei:
            os.makedirs(os.path.join(mei, "tools"))
            exe = os.path.join(mei, "tools", "7za.exe")
            open(exe, "wb").close()
            with mock.patch.object(sys, "_MEIPASS", mei, create=True), \
                    mock.patch.object(extract, "IS_WINDOWS", True):
                self.assertEqual(extract.find_7za(), exe)

    def test_settings_go_to_appdata_on_windows_not_exe_folder(self):
        with tempfile.TemporaryDirectory() as appdata:
            with mock.patch.object(settings, "IS_WINDOWS", True, create=True), \
                    mock.patch.object(settings.os, "name", "nt"), \
                    mock.patch.dict(os.environ, {"APPDATA": appdata}):
                d = settings.settings_dir()
            self.assertEqual(d, os.path.join(appdata, "BasedQuakeInstaller"))


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        import installer_cli
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            installer_cli.main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn(__version__, buf.getvalue())

    def test_self_test_report(self):
        with tempfile.TemporaryDirectory() as d:
            rep = os.path.join(d, "r.json")
            with redirect_stdout(io.StringIO()):
                code = selftest.run(gui=False, report=rep)
            data = json.load(open(rep))
            self.assertEqual(code, 0, data)
            self.assertEqual(data["version"], __version__)
            self.assertTrue(data["checks"]["settings_dir"]["ok"])


if __name__ == "__main__":
    unittest.main()
