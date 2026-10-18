import unittest
from quake_installer import clients
from quake_installer.download import DownloadError

PAGE = ('<a href="https://fastdl.idtech.space/bin/fteqw-win-x86_64-2026-07-13.zip">Win64</a>'
        '<a href="https://fastdl.idtech.space/bin/fteqw-win-x86-2026-07-13.zip">Win32</a>'
        '<a href="https://fastdl.idtech.space/bin/fteqw-linux-x86_64-2026-09-01.zip">Linux</a>'
        '<a href="https://fastdl.idtech.space/bin/fteqw-linux-x86-2026-09-01.zip">x86</a>')


class FteqwOrgTests(unittest.TestCase):
    def test_link_per_platform(self):
        self.assertEqual(clients.latest_fte_link("windows", PAGE)[1], "2026-07-13")
        url, date = clients.latest_fte_link("linux", PAGE)
        self.assertTrue(url.endswith("fteqw-linux-x86_64-2026-09-01.zip"))
        self.assertIsNone(clients.latest_fte_link("linux", "<html></html>"))

    def test_scraped_first_then_pinned_then_triptohell(self):
        urls = clients.fte_urls("linux", fetch_page=lambda u: PAGE)
        self.assertIn("2026-09-01", urls[0])
        self.assertIn("fastdl.idtech.space", urls[1])
        self.assertIn("triptohell", urls[-1])

    def test_page_offline_uses_pinned(self):
        def boom(u): raise OSError("offline")
        meta = clients.resolve_fte("windows", head=lambda u: {"url": u, "size": 1},
                                   fetch_page=boom)
        self.assertEqual(meta["version"], "2026-07-13")
        self.assertEqual(meta["package"], "FTE (fteqw.org)")

    def test_falls_back_to_triptohell(self):
        def head(u):
            if "idtech" in u: raise DownloadError("down")
            return {"url": u, "size": 1}
        meta = clients.resolve_fte("linux", head=head, fetch_page=lambda u: PAGE)
        self.assertIn("triptohell", meta["url"]); self.assertIsNone(meta["version"])
