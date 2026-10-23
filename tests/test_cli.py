import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import installer_cli
from quake_installer import installer, manifest, updater


class CliCorrectnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _run(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = installer_cli.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_check_updates_passes_opts(self):
        with mock.patch.object(installer_cli, "load_specs", return_value=[]), \
                mock.patch.object(updater, "check_updates", return_value=[]) as check:
            code, _out, err = self._run(["--root", self.tmp, "--check-updates"])
        self.assertEqual(code, 0, err)
        self.assertEqual(os.path.normcase(check.call_args[0][0]),
                         os.path.normcase(self.tmp))
        opts = check.call_args[1]["opts"]
        self.assertIsInstance(opts, installer.Options)
        self.assertEqual(os.path.normcase(opts.root), os.path.normcase(self.tmp))

    def test_update_passes_opts_and_reports_install_error(self):
        item = updater.UpdateItem("client:unez", "unezQuake",
                                  manifest.STATUS_OUTDATED)
        with mock.patch.object(installer_cli, "load_specs", return_value=[]), \
                mock.patch.object(updater, "check_updates",
                                  return_value=[item]) as check, \
                mock.patch.object(updater, "apply_updates",
                                  side_effect=installer.InstallError(
                                      "nested folders")) as apply:
            code, _out, err = self._run(["--root", self.tmp, "--update"])
        self.assertEqual(code, 1)
        self.assertIn("ERROR: nested folders", err)
        self.assertIs(apply.call_args[0][0], check.call_args[1]["opts"])

    def test_relative_root_is_rejected(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err), \
                self.assertRaises(SystemExit) as cm:
            installer_cli.main(["--root", "relative", "--check-updates"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("full path", err.getvalue())
