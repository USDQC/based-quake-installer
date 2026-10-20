import hashlib, http.server, io, json, os, shutil, tempfile, threading, unittest, zipfile
import urllib.parse
from quake_installer import download, drive, manifest, mods

FID = "1AbCdEfGhIjKlMnOpQrStUvWxYz012345"

# Shape of Google's current "can't scan for viruses" interstitial (trimmed).
CONFIRM_PAGE = """<!DOCTYPE html><html><head><title>Google Drive - Virus scan warning</title>
<meta http-equiv="content-type" content="text/html; charset=utf-8"/></head><body>
<div class="uc-main"><div id="uc-text"><p class="uc-warning-caption">Google Drive can't
scan this file for viruses.</p><p class="uc-warning-subcaption"><span class="uc-name-size">
<a href="/open?id=%(id)s">fortress.zip</a> (17M)</span> is too large for Google to scan for
viruses. Would you still like to download this file?</p>
<form id="download-form" action="https://drive.usercontent.google.com/download" method="get">
<input type="submit" id="uc-download-link" class="goog-inline-block jfk-button jfk-button-action"
 value="Download anyway"/><input type="hidden" name="id" value="%(id)s"><input type="hidden"
 name="export" value="download"><input type="hidden" name="confirm" value="t"><input
 type="hidden" name="uuid" value="0f1e2d3c-aaaa-bbbb-cccc-123456789abc"></form></div></div>
</body></html>"""

LEGACY_PAGE = ('<html><body><a id="uc-download-link" href="/uc?export=download&amp;'
               'confirm=Xy12&amp;id=%s">Download anyway</a></body></html>' % FID)

SIGNIN_PAGE = ("<html><head><title>Google Drive: Sign-in</title></head><body>"
               "<a href='https://accounts.google.com/ServiceLogin'>Sign in</a></body></html>")


def make_mod_zip(gamedir, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(gamedir + "/" + name, data)
    return buf.getvalue()


class LinkTests(unittest.TestCase):
    def test_share_link_forms(self):
        for url in ("https://drive.google.com/file/d/%s/view?usp=sharing" % FID,
                    "https://drive.google.com/file/d/%s/view" % FID,
                    "https://drive.google.com/open?id=%s" % FID,
                    "https://drive.google.com/uc?id=%s&export=download" % FID,
                    "https://drive.google.com/uc?export=download&id=%s" % FID,
                    "https://drive.usercontent.google.com/download?id=%s&export=download" % FID):
            self.assertEqual(drive.file_id(url), FID, url)
            self.assertEqual(drive.direct_url(url), drive.DIRECT % FID)

    def test_non_drive_untouched(self):
        u = "http://127.0.0.1:8000/fortress.zip?id=%s" % FID
        self.assertIsNone(drive.file_id(u))
        self.assertEqual(drive.direct_url(u), u)
        self.assertIsNone(drive.file_id("PASTE_DRIVE_LINK"))


class ConfirmPageTests(unittest.TestCase):
    def test_virus_scan_form(self):
        u = drive.confirm_url(CONFIRM_PAGE % {"id": FID}, drive.DIRECT % FID)
        p = urllib.parse.urlsplit(u)
        self.assertEqual((p.scheme, p.hostname, p.path),
                         ("https", "drive.usercontent.google.com", "/download"))
        q = dict(urllib.parse.parse_qsl(p.query))
        self.assertEqual(q, {"id": FID, "export": "download", "confirm": "t",
                             "uuid": "0f1e2d3c-aaaa-bbbb-cccc-123456789abc"})

    def test_legacy_confirm_link(self):
        u = drive.confirm_url(LEGACY_PAGE, "https://drive.google.com/uc?id=%s" % FID)
        self.assertEqual(u, "https://drive.google.com/uc?export=download&confirm=Xy12&id=%s"
                         % FID)

    def test_not_shared_page_is_clear_error(self):
        self.assertIsNone(drive.confirm_url(SIGNIN_PAGE, "https://drive.google.com/"))
        with self.assertRaises(download.DownloadError) as cm:
            drive._handler(SIGNIN_PAGE, "https://drive.google.com/")
        self.assertIn("Anyone with the link", str(cm.exception))


class FakeDrive(object):
    """Local HTTP server answering like drive.usercontent.google.com/download:
    first an HTML confirm page, the file only with confirm=t&uuid=<uuid>."""
    UUID = "0f1e2d3c-aaaa-bbbb-cccc-123456789abc"

    def __init__(self, files):
        self.files, self.hits = files, []
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                p = urllib.parse.urlsplit(self.path)
                q = dict(urllib.parse.parse_qsl(p.query))
                fake.hits.append(self.path)
                data = fake.files.get(q.get("id"))
                if data is None:
                    self.send_response(404); self.end_headers(); return
                if q.get("confirm") == "t" and q.get("uuid") == fake.UUID:
                    ctype = "application/json" if q["id"].endswith("json") else \
                        "application/octet-stream"
                    body = data
                else:
                    ctype = "text/html; charset=utf-8"
                    page = CONFIRM_PAGE % {"id": q["id"]}
                    page = page.replace("https://drive.usercontent.google.com/download",
                                        "/download")
                    body = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def url(self, fid):
        return "%s/download?id=%s&export=download" % (self.base, fid)

    def close(self):
        self.srv.shutdown(); self.srv.server_close()


class InstallFromDriveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.zip = make_mod_zip("fortress", {"pak0.pak": b"P" * 1000, "progs.dat": b"x",
                                             "autoexec.cfg": b"bind q quit\r\n"})
        self.drv = FakeDrive({"fortresszipid": self.zip,
                              "indexjson": json.dumps({"format": 1, "mods": [
                                  {"key": "fortress", "version": "9"}]}).encode()})
        self.spec = {"key": "fortress", "title": "TF", "gamedir": "fortress",
                     "clients": ["fte", "unez"], "file": "fortress.zip", "version": "1",
                     "url": self.drv.url("fortresszipid"), "size": len(self.zip),
                     "sha256": hashlib.sha256(self.zip).hexdigest()}
        self.fte, self.unez = os.path.join(self.tmp, "FTE"), os.path.join(self.tmp, "U")

    def tearDown(self):
        self.drv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install(self, spec):
        meta, logs = {}, []
        src = mods.install_mod(spec, self.fte, os.path.join(self.tmp, "w"), log=logs.append,
                               unez_dir=self.unez, meta_out=meta)
        return src, meta, logs

    def test_confirm_page_then_verified_install_both_clients(self):
        src, meta, logs = self._install(self.spec)
        self.assertTrue(any("confirm=t" in h and "uuid=" in h for h in self.drv.hits))
        for root in (self.fte, self.unez):
            self.assertTrue(os.path.isfile(os.path.join(root, "fortress", "pak0.pak")))
            self.assertTrue(os.path.isfile(os.path.join(root, "fortress", "autoexec.cfg")))
        self.assertEqual(meta["sha256"], self.spec["sha256"])
        self.assertIn("sha256 verified", " ".join(logs))
        self.assertTrue(src.startswith("Google Drive"))

    def test_sha_mismatch_installs_nothing(self):
        bad = dict(self.spec, sha256="0" * 64)
        with self.assertRaises(mods.ModError) as cm:
            self._install(bad)
        self.assertIn("sha256 mismatch", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.fte, "fortress")))
        self.assertFalse(os.path.exists(os.path.join(self.unez, "fortress")))

    def test_size_mismatch_and_placeholder(self):
        with self.assertRaises(mods.ModError):
            self._install(dict(self.spec, size=5))
        with self.assertRaises(mods.ModError) as cm:
            self._install(dict(self.spec, url="PASTE_DRIVE_LINK"))
        self.assertIn("no Google Drive link", str(cm.exception))

    def test_zip_without_gamedir_folder_rejected(self):
        z = make_mod_zip("wrong", {"pak0.pak": b"x"})
        self.drv.files["wrongid"] = z
        spec = dict(self.spec, url=self.drv.url("wrongid"), size=len(z),
                    sha256=hashlib.sha256(z).hexdigest())
        with self.assertRaises(mods.ModError) as cm:
            self._install(spec)
        self.assertIn("top-level fortress/", str(cm.exception))

    def test_user_cfg_protected_on_update(self):
        self._install(self.spec)
        mine = os.path.join(self.fte, "fortress", "autoexec.cfg")
        with open(mine, "w") as fh:
            fh.write("// merged by us\n")
        mods.install_mod(self.spec, self.fte, os.path.join(self.tmp, "w"), log=lambda m: None,
                         unez_dir=self.unez, meta_out={}, protect=("autoexec.cfg",))
        self.assertEqual(open(mine).read(), "// merged by us\n")

    def test_index_fetch_retries_dropped_connection(self):
        from unittest import mock
        real, calls = drive._get_text_once, []
        def flaky(*a):
            calls.append(1)
            if len(calls) == 1:
                raise download.DownloadError("GET x failed: RemoteDisconnected")
            return real(*a)
        with mock.patch.object(drive, "_get_text_once", flaky), \
                mock.patch("time.sleep"):
            data = mods.fetch_index(self.drv.url("indexjson"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(mods.index_entries(data)[0]["version"], "9")

    def test_index_through_confirm_page(self):
        data = mods.fetch_index(self.drv.url("indexjson"))
        specs = mods.load_specs(data)
        self.assertEqual({m["key"]: m for m in specs}["fortress"]["version"], "9")


class IndexAndCompareTests(unittest.TestCase):
    def test_builtin_table_complete(self):
        for m in mods.MODS:
            if m.get("binds_only"):
                continue
            self.assertEqual(len(m["sha256"]), 64)
            self.assertGreater(m["size"], 0)
            if mods.is_pack(m):  # Drive link comes via mods.json until pasted in
                self.assertEqual(m["file"], m["key"] + ".zip")
                continue
            self.assertEqual(m["file"], m["gamedir"] + ".zip")
            self.assertEqual(drive.file_id(m["url"]) is not None, True, m["key"])
            self.assertFalse(any(k in m for k in ("mirror_steps", "moddb_files")))

    def test_apply_index_overrides_and_adds(self):
        specs = mods.load_specs({"format": 1, "mods": [
            {"key": "grq", "url": "https://drive.google.com/file/d/%s/view" % FID,
             "sha256": "ab" * 32, "version": "1.1-2", "evil_field": 1},
            {"key": "newmod", "gamedir": "newmod", "url": "u", "sha256": "cd" * 32}]})
        by = {m["key"]: m for m in specs}
        self.assertEqual(by["grq"]["version"], "1.1-2")
        self.assertNotIn("evil_field", by["grq"])
        self.assertEqual(by["newmod"]["file"], "newmod.zip")

    def test_placeholder_in_index_keeps_builtin_link(self):
        builtin = {m["key"]: m for m in mods.MODS}
        specs = mods.load_specs({"format": 1, "mods": [
            {"key": "grq", "url": "PASTE_DRIVE_LINK", "sha256": builtin["grq"]["sha256"],
             "version": "1.1"},
            {"key": "arena", "url": "", "version": "1.2"}]})
        by = {m["key"]: m for m in specs}
        self.assertEqual(by["grq"]["url"], builtin["grq"]["url"])
        self.assertEqual(by["arena"]["url"], builtin["arena"]["url"])
        self.assertTrue(by["grq"]["url"].startswith("https://drive.google.com/file/d/"))

    def test_compare_sha_and_version(self):
        c = manifest.compare
        inst = {"sha256": "AA" * 32, "version": "1"}
        self.assertEqual(c(inst, {"sha256": "aa" * 32, "version": "1"}), manifest.STATUS_OK)
        self.assertEqual(c(inst, {"sha256": "bb" * 32, "version": "1"}),
                         manifest.STATUS_OUTDATED)
        self.assertEqual(c(inst, {"sha256": "aa" * 32, "version": "2"}),
                         manifest.STATUS_OUTDATED)
        self.assertEqual(c({"steps": []}, {"sha256": "aa" * 32}), manifest.STATUS_OUTDATED)

    def test_index_placeholder_means_builtin(self):
        from unittest import mock
        old = os.environ.pop("BASED_QUAKE_MODS_INDEX", None)
        try:
            with mock.patch.object(mods, "MODS_INDEX_URL", mods.PLACEHOLDER):
                self.assertIsNone(mods.index_url())
                specs, err = mods.load_specs_online(log=lambda m: None)
            self.assertIsNone(err)
            self.assertEqual(len(specs), len(mods.MODS))
            self.assertIsNotNone(drive.file_id(mods.MODS_INDEX_URL))  # the real USDQC Drive link
        finally:
            if old is not None:
                os.environ["BASED_QUAKE_MODS_INDEX"] = old

if __name__ == "__main__":
    unittest.main()


class BuilderTests(unittest.TestCase):
    def setUp(self):
        import importlib.util, sys
        p = os.path.join(os.path.dirname(__file__), "..", "packaging", "drive",
                         "build_drive_zips.py")
        spec = importlib.util.spec_from_file_location("build_drive_zips", p)
        self.b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.b)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _w(self, rel, data="x"):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(data)

    def test_refuses_generated_and_uppercase(self):
        self._w("g/autoexec.cfg", "exec based.cfg\nexec binds.cfg\n")
        self._w("g/binds.cfg")
        self._w("g/PAK0.PAK")
        self._w("g/extra.7z")
        probs = " ".join(self.b.check_clean(os.path.join(self.tmp, "g")))
        for word in ("merged", "binds.cfg", "uppercase", "nested"):
            self.assertIn(word, probs)

    def test_deterministic_zip_with_gamedir_top(self):
        self._w("g/pak0.pak", "P" * 100)
        self._w("g/maps/a.bsp")
        self._w("g/autoexec.cfg", "bind q quit\n")  # mod's own cfg is fine
        self.assertEqual(self.b.check_clean(os.path.join(self.tmp, "g")), [])
        z1, z2 = os.path.join(self.tmp, "1.zip"), os.path.join(self.tmp, "2.zip")
        self.b.make_zip(os.path.join(self.tmp, "g"), "g", z1)
        os.utime(os.path.join(self.tmp, "g", "pak0.pak"), (1, 1))
        self.b.make_zip(os.path.join(self.tmp, "g"), "g", z2)
        self.assertEqual(self.b.sha256(z1), self.b.sha256(z2))
        names = zipfile.ZipFile(z1).namelist()
        self.assertTrue(all(n.startswith("g/") for n in names))
        self.assertIn("g/maps/a.bsp", names)
