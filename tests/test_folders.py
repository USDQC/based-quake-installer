import os
import shutil
import tempfile
import unittest

from quake_installer import folders, installer, manifest, updater


def ok(root, u, f, windows, **kw):
    folders.check_engine_folders(root, u, f, windows=windows, **kw)


class FullPathTests(unittest.TestCase):
    def test_windows_paths(self):
        self.assertTrue(folders.is_full_path("C:\\Games", windows=True))
        self.assertTrue(folders.is_full_path("c:/Games", windows=True))
        self.assertTrue(folders.is_full_path("\\\\server\\share\\q", windows=True))
        self.assertTrue(folders.is_full_path("//server/share/q", windows=True))
        self.assertFalse(folders.is_full_path("C:foo", windows=True))
        self.assertFalse(folders.is_full_path("Games\\q", windows=True))
        self.assertFalse(folders.is_full_path("\\Games", windows=True))
        self.assertFalse(folders.is_full_path("", windows=True))
        self.assertTrue(folders.is_full_path(' "C:\\Games" ', windows=True))

    def test_posix_paths(self):
        self.assertTrue(folders.is_full_path("/home/q", windows=False))
        self.assertFalse(folders.is_full_path("q/games", windows=False))


class WindowsRulesTests(unittest.TestCase):
    W = True
    R = "C:\\Games"

    def bad(self, u, f, root=None, text=None, **kw):
        with self.assertRaises(folders.FolderError) as cm:
            ok(root or self.R, u, f, self.W, **kw)
        if text:
            self.assertIn(text, str(cm.exception))

    def test_defaults_are_fine(self):
        ok(self.R, "C:\\Games\\unezQuake", "C:\\Games\\FTE", self.W)
        ok(self.R, "D:\\ez", "E:\\fte", self.W)
        ok(self.R, None, "C:\\Games\\FTE", self.W)

    def test_equal_is_forbidden(self):
        self.bad("D:\\Q", "D:\\Q", text="unezQuake and FTE need their own separate folders")
        self.bad("D:\\Quake\\Engine", "d:/QUAKE/engine/", text="separate folders")

    def test_same_folder_helper(self):
        self.assertTrue(folders.same_folder("C:\\nQuake", "c:/nquake/", windows=True))
        self.assertFalse(folders.same_folder("C:\\nQuake", "C:\\fteqw", windows=True))

    def test_nested_both_ways(self):
        self.bad("D:\\Q", "D:\\Q\\fte", text="inside the unezQuake folder")
        self.bad("D:\\Q\\ez", "D:\\Q", text="inside the FTE folder")

    def test_prefix_is_not_nesting(self):
        ok(self.R, "D:\\Q", "D:\\Q2", self.W)

    def test_equals_root_is_forbidden(self):
        self.bad("C:\\games", None, text="same as the install folder")
        self.bad(None, "C:\\Games\\", text="same as the install folder")
        self.bad("C:\\nQuake", "C:\\fteqw", root="C:\\nQuake", text="same as the install folder")

    def test_ancestor_of_root(self):
        self.bad("C:\\", None, text="contain the install folder")
        self.bad(None, "c:\\", text="contain the install folder")

    def test_inside_other_default(self):
        self.bad("C:\\Games\\FTE\\ez", None, text="FTE folder")
        self.bad("C:\\Games\\unezQuake", "C:\\GAMES\\UNEZQUAKE\\fte")
        self.bad(None, "C:\\Games\\unezQuake")

    def test_off_engine_checks_installed(self):
        self.bad("C:\\Games\\FTE\\ez", None, installed={"fte": "C:\\Games\\FTE"},
                 text="FTE folder")
        self.bad(None, "C:\\Elsewhere", installed={"unez": "C:\\Elsewhere\\unezQuake"},
                 text="unezQuake folder")
        self.bad("C:\\Games\\unezQuake", None,
                 installed={"fte": "C:\\Games\\unezQuake\\fte"}, text="FTE folder")
    def test_unc(self):
        ok("\\\\nas\\q", "\\\\nas\\q\\unezQuake", "//nas/q/FTE", self.W)
        self.bad("\\\\nas\\q\\a", "//NAS/q/a/b", root="\\\\nas\\q")

    def test_existing_mode(self):
        folders.check_existing_folders("D:\\ez", "E:\\fte", windows=True)
        folders.check_existing_folders("D:\\ez", None, windows=True)
        for u, f in (("D:\\Q", "d:\\q"), ("D:\\Q", "D:\\Q\\fte"), ("D:\\Q\\e", "D:\\Q")):
            with self.assertRaises(folders.FolderError):
                folders.check_existing_folders(u, f, windows=True)


class HostRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_symlink_resolves_to_same_folder(self):
        if not hasattr(os, "symlink"):
            self.skipTest("no symlinks")
        real = os.path.join(self.tmp, "real")
        os.makedirs(real)
        link = os.path.join(self.tmp, "link")
        try:
            os.symlink(real, link)
        except OSError:
            self.skipTest("symlinks not allowed")
        self.assertTrue(folders.same_folder(real, link))
        with self.assertRaises(folders.FolderError):
            folders.check_existing_folders(real, link)

    def test_backend_rejects_shared_folder(self):
        same = os.path.join(self.tmp, "both")
        opts = installer.Options(self.tmp, "p", "soft", unez_target=same, fte_target=same)
        with self.assertRaises(installer.InstallError) as cm:
            opts.check_folders()
        self.assertIn("separate folders", str(cm.exception))
        self.assertFalse(os.path.exists(same))  # check only; nothing created

    def test_backend_rejects_root_as_target(self):
        opts = installer.Options(self.tmp, "p", "soft", unez_target=self.tmp,
                                 install_fte=False)
        with self.assertRaises(installer.InstallError):
            opts.check_folders()

    def test_mods_only_rejects_nested(self):
        a = os.path.join(self.tmp, "a")
        os.makedirs(os.path.join(a, "b"))
        opts = installer.Options(self.tmp, "p", "soft", existing=True, unez_path=a,
                                 fte_path=os.path.join(a, "b"))
        with self.assertRaises(installer.InstallError):
            installer.run_install(opts, installer.Reporter())

    def test_mods_only_rejects_shared(self):
        a = os.path.join(self.tmp, "a")
        opts = installer.Options(self.tmp, "p", "soft", existing=True, unez_path=a,
                                 fte_path=a)
        with self.assertRaises(installer.InstallError) as cm:
            opts.check_folders()
        self.assertIn("separate folders", str(cm.exception))


class ManifestDirsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _opts(self, **kw):
        return installer.Options(self.tmp, "p", "soft", platform="linux", **kw)

    def test_record_engines(self):
        ez = os.path.join(self.tmp, "ez")
        man = manifest.record_engines(manifest.empty(), self._opts(
            unez_target=ez, install_fte=False))
        self.assertEqual(man["engine_dirs"], {"unez": os.path.abspath(ez)})
        self.assertEqual(man["engines_selected"], {"unez": True, "fte": False})

    def test_turned_off_engine_keeps_its_recorded_folder(self):
        fte = os.path.join(self.tmp, "fte")
        man = manifest.record_engines(manifest.empty(), self._opts(fte_target=fte))
        man = manifest.record_engines(man, self._opts(install_fte=False))
        self.assertEqual(man["engine_dirs"]["fte"], os.path.abspath(fte))

    def test_updates_prefer_recorded_dirs(self):
        ez = os.path.join(self.tmp, "custom-ez")
        man = manifest.record_engines(manifest.empty(), self._opts(unez_target=ez))
        manifest.save(self.tmp, man)
        opts = self._opts()  # Remember folders off / settings lost: no target
        opts.use_manifest_dirs(override=True)
        self.assertEqual(opts.unez_dir, ez)
        self.assertEqual(opts.fte_dir, os.path.join(self.tmp, "FTE"))
        opts = self._opts(unez_target=os.path.join(self.tmp, "other"))
        opts.use_manifest_dirs(override=True)
        self.assertEqual(opts.unez_dir, ez)

    def test_install_uses_recorded_dir_only_when_no_folder_chosen(self):
        ez = os.path.join(self.tmp, "custom-ez")
        manifest.save(self.tmp, manifest.record_engines(
            manifest.empty(), self._opts(unez_target=ez)))
        opts = self._opts()
        opts.use_manifest_dirs()
        self.assertEqual(opts.unez_dir, ez)
        mine = os.path.join(self.tmp, "mine")
        opts = self._opts(unez_target=mine)
        opts.use_manifest_dirs()
        self.assertEqual(opts.unez_dir, mine)

    def test_old_manifest_falls_back_to_defaults(self):
        man = manifest.empty("linux")
        manifest.record(man, "client:unez", {"version": "1"})
        manifest.save(self.tmp, man)
        self.assertEqual(manifest.engine_dirs(manifest.load(self.tmp)), {})
        opts = self._opts()
        opts.use_manifest_dirs(override=True)
        self.assertEqual(opts.unez_dir, os.path.join(self.tmp, "unezQuake"))
        self.assertEqual(manifest.engine_dirs({"engine_dirs": "junk"}), {})
        self.assertEqual(manifest.engine_folders(man, self.tmp), {
            "unez": os.path.join(self.tmp, "unezQuake")})

    def test_engine_folders_keeps_recorded_dirs(self):
        ez = os.path.join(self.tmp, "custom-ez")
        man = manifest.record_engines(manifest.empty("linux"),
                                      self._opts(unez_target=ez, install_fte=False))
        self.assertEqual(manifest.engine_folders(man, self.tmp),
                         {"unez": os.path.abspath(ez)})

    def test_check_updates_uses_recorded_dir(self):
        ez = os.path.join(self.tmp, "custom-ez")
        manifest.save(self.tmp, manifest.record_engines(
            manifest.empty("linux"), self._opts(unez_target=ez)))
        opts = self._opts()
        updater.check_updates(self.tmp, "linux", specs=[], log=lambda *a: None, opts=opts,
                              resolve_unez=lambda p: None, resolve_fte=lambda p: None)
        self.assertEqual(opts.unez_dir, ez)


class TurnedOffNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _opts(self, **kw):
        return installer.Options(self.tmp, "p", "soft", platform="linux", **kw)

    def test_nothing_when_all_on(self):
        os.makedirs(os.path.join(self.tmp, "FTE"))
        self.assertEqual(updater.turned_off_notes(self.tmp, self._opts()), [])

    def test_installed_on_disk_but_off(self):
        os.makedirs(os.path.join(self.tmp, "FTE"))
        notes = updater.turned_off_notes(self.tmp, self._opts(install_fte=False))
        self.assertEqual(notes, ["FTE is installed but turned off in Settings, so it "
                                 "won't be updated."])
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "FTE")))  # nothing deleted

    def test_installed_per_manifest_but_off(self):
        man = manifest.empty("linux")
        manifest.record(man, "client:unez", {"version": "1"})
        manifest.save(self.tmp, man)
        notes = updater.turned_off_notes(self.tmp, self._opts(install_unez=False))
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("unezQuake is installed but turned off"))

    def test_recorded_folder_counts(self):
        fte = os.path.join(self.tmp, "elsewhere-fte")
        os.makedirs(fte)
        manifest.save(self.tmp, manifest.record_engines(
            manifest.empty(), self._opts(fte_target=fte)))
        self.assertEqual(len(updater.turned_off_notes(
            self.tmp, self._opts(install_fte=False))), 1)

    def test_not_installed_and_off(self):
        self.assertEqual(updater.turned_off_notes(self.tmp, self._opts(install_fte=False)), [])

    def test_shared_folder_does_not_fake_a_note(self):
        # Legacy shared-folder installs: don't invent a turned-off note for the
        # other engine just because the same folder is on disk.
        shared = os.path.join(self.tmp, "shared")
        os.makedirs(shared)
        man = manifest.record_engines(
            manifest.empty(), self._opts(unez_target=shared, install_fte=False))
        # Simulate an old manifest that recorded both engines in one folder.
        man["engine_dirs"] = {"unez": os.path.abspath(shared),
                              "fte": os.path.abspath(shared)}
        manifest.record(man, "client:unez", {"version": "1"})
        manifest.save(self.tmp, man)
        self.assertEqual(updater.turned_off_notes(
            self.tmp, self._opts(install_fte=False)), [])
        manifest.record(man, "client:fte", {"version": "1"})
        manifest.save(self.tmp, man)
        self.assertEqual(len(updater.turned_off_notes(
            self.tmp, self._opts(install_fte=False))), 1)

    def test_mods_only_has_no_notes(self):
        opts = installer.Options(self.tmp, "p", "soft", existing=True, unez_path=self.tmp)
        self.assertEqual(updater.turned_off_notes(self.tmp, opts), [])
