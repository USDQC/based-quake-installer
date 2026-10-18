"""Google Drive downloads for mod zips and mods.json.

Share links are turned into direct downloads:
    https://drive.google.com/file/d/<id>/view?usp=sharing
    https://drive.google.com/open?id=<id>
    https://drive.google.com/uc?id=<id>&export=download
    https://drive.usercontent.google.com/download?id=<id>...
  -> https://drive.usercontent.google.com/download?id=<id>&export=download

Large files (Drive can't virus-scan them) first return an HTML "Download anyway"
page. Its <form id="download-form" action=".../download"> carries hidden inputs
(id, export, confirm, uuid); submitting that form (GET) returns the file. Older
pages used a link "/uc?export=download&confirm=XXXX&id=..."; both are handled.
Any other URL (a self-hosted mirror, the test server) is downloaded as is.
"""

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from . import download as dl
from .constants import USER_AGENT
from .download import DownloadError

DIRECT = "https://drive.usercontent.google.com/download?id=%s&export=download"
_ID = r"[A-Za-z0-9_-]{10,}"


def is_drive(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host in ("drive.google.com", "docs.google.com", "drive.usercontent.google.com")


def file_id(url):
    """The Drive file id in a share/direct link, else None."""
    if not is_drive(url):
        return None
    parts = urllib.parse.urlsplit(url)
    m = re.search(r"/file/d/(%s)" % _ID, parts.path) or \
        re.search(r"/(?:document|spreadsheets|presentation)/d/(%s)" % _ID, parts.path)
    if m:
        return m.group(1)
    q = urllib.parse.parse_qs(parts.query)
    for v in q.get("id", []):
        if re.fullmatch(_ID, v):
            return v
    return None


def direct_url(url):
    fid = file_id(url)
    return DIRECT % fid if fid else url


def describe(url):
    fid = file_id(url)
    return "Google Drive (id %s)" % fid if fid else url


class _FormParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.forms = []      # [(attrs, {name: value})]
        self.links = []
        self._cur = None

    def handle_starttag(self, tag, attrs):
        a = dict((k, v or "") for k, v in attrs)
        if tag == "form":
            self._cur = (a, {})
            self.forms.append(self._cur)
        elif tag == "input" and self._cur is not None and a.get("name"):
            if a.get("type", "text").lower() in ("hidden", "text"):
                self._cur[1][a["name"]] = a.get("value", "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self._cur = None


def confirm_url(page, base_url):
    """URL that confirms a Drive virus-scan warning page, or None if the page is not one."""
    p = _FormParser()
    try:
        p.feed(page)
    except Exception:
        return None
    for attrs, fields in p.forms:
        action = html.unescape(attrs.get("action", ""))
        if (attrs.get("id") == "download-form" or "/download" in action or "/uc" in action) \
                and fields.get("id"):
            act = urllib.parse.urljoin(base_url, action or "/download")
            if (attrs.get("method") or "get").lower() != "get":
                return None
            return act + ("&" if "?" in act else "?") + urllib.parse.urlencode(fields)
    for href in p.links:
        h = html.unescape(href)
        if "confirm=" in h and ("export=download" in h or "/download" in h):
            return urllib.parse.urljoin(base_url, h)
    return None


def _html_error(page):
    t = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    title = html.unescape(t.group(1)).strip() if t else "a web page"
    low = page.lower()
    if "quota" in low and "exceed" in low:
        hint = "Drive download quota exceeded for this file; try again in 24h"
    elif "sign in" in low or "accounts.google.com" in low or "request access" in low:
        hint = "the file is not shared as 'Anyone with the link'"
    else:
        hint = "not a file download"
    return "Google Drive returned %r instead of the file (%s)" % (title, hint)


def _handler(page, url):
    nxt = confirm_url(page, url)
    if not nxt:
        raise DownloadError(_html_error(page))
    return nxt


def download(url, dest, progress=None, cancel_event=None, log=None, retries=2):
    """Download a Drive share link (or any URL) to dest, passing Drive's confirm page.
    A mod zip is never HTML, so any HTML answer is treated as an interstitial."""
    return dl.download(direct_url(url), dest, progress=progress, cancel_event=cancel_event,
                       retries=retries, html_handler=_handler)


def get_text(url, timeout=30, max_bytes=2 << 20, retries=2):
    """GET a small text file (mods.json) through Drive, following the confirm page.
    Retries dropped connections (Drive occasionally resets them)."""
    import time
    for attempt in range(retries + 1):
        try:
            return _get_text_once(url, timeout, max_bytes)
        except DownloadError as exc:
            if attempt >= retries or "too large" in str(exc) or "instead of the file" in str(exc):
                raise
            time.sleep(1.5 * (attempt + 1))


def _get_text_once(url, timeout, max_bytes):
    cur = direct_url(url)
    for _hop in range(3):
        req = urllib.request.Request(cur, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(max_bytes + 1)
                ctype = (resp.headers.get("Content-Type") or "").lower()
                final = resp.geturl()
        except Exception as exc:
            raise DownloadError("GET %s failed: %s" % (url, dl._friendly(exc)))
        if len(body) > max_bytes:
            raise DownloadError("%s: response too large for mods.json" % url)
        text = body.decode("utf-8", "replace")
        if "text/html" in ctype:  # mods.json is never HTML: a Drive interstitial
            cur = _handler(text, final)
            continue
        return text
    raise DownloadError("%s: too many Drive confirm pages" % url)
