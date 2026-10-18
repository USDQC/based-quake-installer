"""HTTP download with progress, retries, mirrors and cancel support (urllib only)."""

import os
import socket
import ssl
import time
import urllib.error
import urllib.request

from .constants import USER_AGENT


class DownloadError(Exception):
    pass


class Cancelled(Exception):
    pass


def _friendly(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return "HTTP %d %s" % (exc.code, exc.reason)
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return ("SSL error (%s). If you are behind a proxy/antivirus that inspects "
                    "HTTPS, allow this download or try again later." % reason)
        if isinstance(reason, socket.gaierror):
            return "Cannot resolve host (no internet / DNS problem): %s" % reason
        return "Network error: %s" % reason
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "Timed out waiting for the server"
    return "%s: %s" % (type(exc).__name__, exc)


def _open_following_html(url, timeout, html_handler, max_hops=3):
    """urlopen url; while it answers text/html and html_handler is set, let the handler
    turn the page into the next URL (Google Drive's virus-scan confirm form)."""
    cur = url
    for _hop in range(max_hops + 1):
        req = urllib.request.Request(cur, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=timeout)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if html_handler is None or "text/html" not in ctype:
            return resp
        try:
            page = resp.read(2 << 20).decode("utf-8", "replace")
            final = resp.geturl()
        finally:
            resp.close()
        cur = html_handler(page, final)  # raises DownloadError when it is not a confirm page
    raise DownloadError("Too many HTML pages before the file (%s)" % url)


def download(url, dest, progress=None, cancel_event=None, timeout=60, retries=2,
             html_handler=None):
    """Download ``url`` to ``dest``.

    progress(done_bytes, total_bytes_or_None) is called periodically.
    html_handler(page_text, page_url) -> next_url is used when the server answers with
    an HTML page instead of the file (see drive.py).
    Raises DownloadError with a readable message, or Cancelled.
    """
    last_err = None
    for attempt in range(1, retries + 2):
        if cancel_event is not None and cancel_event.is_set():
            raise Cancelled()
        tmp = dest + ".part"
        try:
            with _open_following_html(url, timeout, html_handler) as resp:
                total = resp.headers.get("Content-Length")
                total = int(total) if total and total.isdigit() else None
                done = 0
                last_report = 0.0
                with open(tmp, "wb") as fh:
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            raise Cancelled()
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if progress and (now - last_report > 0.1):
                            progress(done, total)
                            last_report = now
                if progress:
                    progress(done, total)
            if total is not None and done != total:
                raise DownloadError("Incomplete download: got %d of %d bytes" % (done, total))
            if done == 0:
                raise DownloadError("Server returned an empty file")
            if os.path.exists(dest):
                os.remove(dest)
            os.replace(tmp, dest)
            return dest
        except Cancelled:
            _silent_remove(tmp)
            raise
        except DownloadError as exc:
            last_err = str(exc)
        except Exception as exc:  # network / IO
            last_err = _friendly(exc)
        _silent_remove(tmp)
        if attempt <= retries:
            time.sleep(1.5 * attempt)
    raise DownloadError("Download failed for %s\n  %s" % (url, last_err))


def download_first(urls, dest, progress=None, cancel_event=None, log=None):
    """Try each mirror in turn; return the URL that worked."""
    errors = []
    for url in urls:
        try:
            if log:
                log("  trying %s" % url)
            download(url, dest, progress=progress, cancel_event=cancel_event, retries=1)
            return url
        except Cancelled:
            raise
        except DownloadError as exc:
            errors.append(str(exc))
            if log:
                log("  mirror failed: %s" % url)
    raise DownloadError("All mirrors failed:\n  " + "\n  ".join(errors))


def _silent_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def head(url, timeout=20):
    """HEAD a URL (following redirects). Returns {url,size,etag,last_modified}.

    Raises DownloadError with a readable message when offline / not found.
    """
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            h = resp.headers
            size = h.get("Content-Length")
            return {
                "url": url,
                "final_url": resp.geturl(),
                "size": int(size) if size and size.isdigit() else None,
                "etag": (h.get("ETag") or "").strip() or None,
                "last_modified": h.get("Last-Modified"),
            }
    except Exception as exc:
        raise DownloadError("HEAD %s failed: %s" % (url, _friendly(exc)))


def get_json(url, timeout=20):
    import json
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise DownloadError("GET %s failed: %s" % (url, _friendly(exc)))
