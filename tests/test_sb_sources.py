import os, shutil, tempfile, unittest
from unittest import mock
from quake_installer import cfg, installer, sb_sources


class Rep(object):
    def __init__(self): self.lines = []
    def log(self, m): self.lines.append(m)
    def step(self, *a): pass
    def progress(self, *a): pass


def entries(text):
    return [e for e in (sb_sources.parse_line(l) for l in text.split("\n")) if e]


class ParseTests(unittest.TestCase):
    def test_formats(self):
        P = sb_sources.parse_line
        self.assertEqual(P('master "Asgaard" qwmaster.fodquake.net:27000'),
                         ("master", "Asgaard", "qwmaster.fodquake.net:27000"))
        self.assertEqual(P("file Global global.txt"), ("file", "Global", "global.txt"))
        self.assertEqual(P('url "A B" http://x/y.txt  '), ("url", "A B", "http://x/y.txt"))
        self.assertIsNone(P('// master "x" 1.2.3.4:27000'))
        self.assertIsNone(P("bogus \"x\" y"))
        self.assertIsNone(P(""))


class MergeTests(unittest.TestCase):
    def test_fresh_has_all_defaults(self):
        got = entries(sb_sources.merge(None))
        self.assertEqual(got, list(sb_sources.DEFAULT_SOURCES))

    def test_keeps_user_entries_and_dedupes(self):
        user = ('// my list\r\n'
                'master "My Master" MASTER.QuakeServers.net:27000\r\n'
                'master "Mine" 10.0.0.1:27000\r\n'
                'master "Mine again" 10.0.0.1:27000\r\n'
                'url "QS" http://www.quakeservers.net/lists/servers/global.txt/\r\n')
        out = sb_sources.merge(user)
        got = entries(out)
        self.assertIn("// my list", out)
        addrs = [e[2].lower() for e in got]
        self.assertEqual(addrs.count("10.0.0.1:27000"), 1)            # dup dropped
        self.assertIn(("master", "My Master", "MASTER.QuakeServers.net:27000"), got)
        self.assertNotIn("QuakeServers.net", [e[1] for e in got])     # user's name kept
        self.assertEqual(sum(e[0] == "url" for e in got), 1)          # http==https, slash
        self.assertIn(("master", "QuakeWorld.nu", "master.quakeworld.nu:27000"), got)
        self.assertEqual(sb_sources.merge(out), out)                  # idempotent


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.unez = os.path.join(self.tmp, "unezQuake")
        os.makedirs(self.unez)
        self.path = os.path.join(self.unez, "ezquake", "sb", "sources.txt")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_then_unchanged_then_bak(self):
        rep = Rep()
        self.assertEqual(sb_sources.write_sources(self.unez, rep.log), self.path)
        self.assertFalse(os.path.exists(self.path + ".bak"))
        sb_sources.write_sources(self.unez, rep.log)                  # unchanged
        self.assertFalse(os.path.exists(self.path + ".bak"))
        self.assertTrue(any("unchanged" in l for l in rep.lines))
        with open(self.path, "a") as fh:
            fh.write('master "Mine" 10.0.0.1:27000\nmaster "Dup" 10.0.0.1:27000\n')
        before = open(self.path).read()
        sb_sources.write_sources(self.unez, rep.log)
        self.assertEqual(open(self.path + ".bak").read(), before)
        txt = open(self.path).read()
        self.assertIn('"Mine"', txt)
        self.assertNotIn('"Dup"', txt)

    def test_dead_entry_kept_with_note(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as fh:
            fh.write('master "Poland" 217.153.59.106:27000\n')
        rep = Rep()
        sb_sources.write_sources(self.unez, rep.log)
        self.assertIn("Poland", open(self.path).read())
        self.assertTrue(any("NOTE" in l and "Poland" in l for l in rep.lines))

    def test_configs_only_install_writes_sources_and_marks(self):
        os.makedirs(os.path.join(self.tmp, "FTE"))
        o = installer.Options(self.tmp, "Ranger", "soft", binds={})
        o.configs_only = True
        with mock.patch.object(installer, "find_unez", return_value="unezquake"), \
                mock.patch.object(installer, "find_fte", return_value=None):
            res = installer.run_install(o, Rep())
        self.assertIn(self.path, res.cfg_files)
        self.assertEqual(len(entries(open(self.path).read())), len(sb_sources.DEFAULT_SOURCES))
        based = open(os.path.join(self.unez, "id1", "based.cfg")).read()
        for _t, name, _a in sb_sources.DEFAULT_SOURCES:
            self.assertIn('sb_sourcemark "%s"' % name, based)
        fte_based = open(os.path.join(self.tmp, "FTE", "id1", "based.cfg")).read()
        self.assertNotIn("sb_sourcemark", fte_based)

    def test_unez_update_path_writes_sources(self):
        o = installer.Options(self.tmp, "Ranger", "soft", binds={})
        man = {}
        with mock.patch.object(installer.download, "download"), \
                mock.patch.object(installer.clients, "install_unez",
                                  return_value=("unezquake", ["unezquake"])):
            installer.install_unez_build(o, Rep(), installer.Result(), self.tmp, man,
                                         {"url": "http://x/unez.zip", "version": "t"})
        self.assertTrue(os.path.isfile(self.path))

    def test_sources_protected_from_zip_overwrite(self):
        self.assertIn("sources.txt", installer.PROTECTED_FILES)


if __name__ == "__main__":
    unittest.main()
