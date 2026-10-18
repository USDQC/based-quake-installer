"""Engine clients per platform: resolve latest builds, download + install them.

unezQuake: GitHub releases API (dusty-qw/unezquake latest), asset per platform.
FTE: the newest dated build linked from https://www.fteqw.org/ (fastdl.idtech.space),
version = build date; a pinned official build and the old fte.triptohell.info
AfterQuake / engine zips are fallbacks only. Windows x64 and Linux x64 only.
"""

import os
import zipfile

from . import download, extract
from .constants import (
    FTE_EXE_BY_PLATFORM, FTEQW_ORG, PLATFORM_BUILDS, PLATFORM_LABELS,
    PROTECTED_FILES, UNEZ_EXE_BY_PLATFORM, UNEZ_FALLBACK_TAG, UNEZ_RELEASES_API,
)
from .download import DownloadError


class ClientError(Exception):
    pass


def platform_label(platform):
    return PLATFORM_LABELS.get(platform, platform)


def unez_asset_name(platform):
    return PLATFORM_BUILDS[platform]["unez_asset"]


_FTE_LINK_RE = r'https?://[^"\'<> ]*/fteqw-%s-(\d{4}-\d{2}-\d{2})\.zip'


def latest_fte_link(platform, page_text):
    """(url, date) of the newest fteqw.org download link for platform, or None."""
    import re
    key = PLATFORM_BUILDS[platform].get("fte_key")
    if not key or not page_text:
        return None
    found = [(m.group(1), m.group(0)) for m in
             re.finditer(_FTE_LINK_RE % re.escape(key), page_text)]
    if not found:
        return None
    date, url = max(found)
    return url, date


def _fetch_text(url, timeout=20):
    import urllib.request
    from .constants import USER_AGENT
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(512 * 1024).decode("utf-8", "replace")


def fte_urls(platform, fetch_page=None):
    """Official fteqw.org build first (scraped from the download page, so a newer dated
    build is picked up), then the pinned official build, then triptohell fallbacks."""
    urls = list(PLATFORM_BUILDS[platform]["fte_urls"])
    if fetch_page is None:
        return urls
    try:
        hit = latest_fte_link(platform, fetch_page(FTEQW_ORG))
    except Exception:  # noqa: BLE001 - page offline/changed: use the pinned list
        hit = None
    if hit and hit[0] not in urls:
        urls.insert(0, hit[0])
    return urls


def _fallback_unez_url(platform):
    return "https://github.com/dusty-qw/unezquake/releases/download/%s/%s" % (
        UNEZ_FALLBACK_TAG, unez_asset_name(platform))


def resolve_unez(platform, get_json=download.get_json, head=download.head):
    """Latest unezQuake meta for platform, or None if there is no asset for it.

    Falls back to the pinned release when the GitHub API is unreachable/rate-limited.
    Raises DownloadError when nothing at all can be reached (offline).
    """
    want = unez_asset_name(platform)
    if not want:
        return None
    try:
        rel = get_json(UNEZ_RELEASES_API)
        tag = rel.get("tag_name")
        for a in rel.get("assets") or []:
            if a.get("name", "").lower() == want.lower():
                return {"version": tag, "url": a["browser_download_url"],
                        "size": a.get("size"), "etag": None,
                        "last_modified": a.get("updated_at"), "asset": a["name"]}
        return None  # release exists but has no build for this platform
    except DownloadError:
        url = _fallback_unez_url(platform)
        meta = head(url)
        meta.update({"version": UNEZ_FALLBACK_TAG, "asset": want, "url": url})
        return meta


def resolve_fte(platform, head=download.head, fetch_page=_fetch_text):
    """First reachable FTE build for platform (meta incl. url), or None if no build.
    version = build date for official fteqw.org builds (fteqw-<plat>-YYYY-MM-DD.zip)."""
    import re
    urls = fte_urls(platform, fetch_page=fetch_page)
    if not urls:
        return None
    errors = []
    for url in urls:
        try:
            meta = head(url)
            m = re.search(r"fteqw-[a-z0-9_-]+?-(\d{4}-\d{2}-\d{2})\.zip$", url)
            meta["version"] = m.group(1) if m else None
            meta["package"] = ("AfterQuake" if "afterquake" in url else
                               "FTE (fteqw.org)" if m else "FTE engine-only")
            return meta
        except DownloadError as exc:
            errors.append(str(exc))
    raise DownloadError("; ".join(errors))


def _expand_nested_zips(stage):
    """Unpack a single zip nested inside the release zip in place (defensive)."""
    for _ in range(2):
        items = [i for i in os.listdir(stage) if not i.startswith("__MACOSX")]
        inner = [i for i in items if i.lower().endswith(".zip")]
        if len(items) == 1 and len(inner) == 1:
            p = os.path.join(stage, inner[0])
            if zipfile.is_zipfile(p):
                extract.safe_extract_zip(p, stage)
                os.remove(p)
                continue
        break


def _copy_listing(src):
    out = []
    for root, _d, files in os.walk(src):
        for f in files:
            out.append(os.path.relpath(os.path.join(root, f), src).replace(os.sep, "/"))
    return sorted(out)


def install_unez(platform, zip_path, unez_dir, stage, protect=PROTECTED_FILES, log=print):
    """Extract a unezQuake build into unez_dir. Returns (exe_name, files)."""
    extract.safe_extract_zip(zip_path, stage)
    _expand_nested_zips(stage)
    src_dir, exe = extract.find_unez_exe_dir(stage, UNEZ_EXE_BY_PLATFORM[platform])
    if not exe:
        raise ClientError("unezQuake executable not found in %s" % os.path.basename(zip_path))
    skipped = []
    extract.copy_tree_over(src_dir, unez_dir, protect=protect, skipped=skipped)
    files = _copy_listing(src_dir)
    exe_path = os.path.join(unez_dir, exe)
    if not exe.lower().endswith(".exe"):
        extract.mark_executable(exe_path)
    for s in skipped:
        log("  kept your %s" % s)
    return exe, files


def install_fte(platform, zip_path, fte_dir, stage, protect=PROTECTED_FILES, log=print):
    """Extract an FTE build into fte_dir. Returns (exe_name, files)."""
    extract.safe_extract_zip(zip_path, stage)
    root = extract.flatten_root(stage)
    skipped = []
    extract.copy_tree_over(root, fte_dir, protect=protect, skipped=skipped)
    os.makedirs(os.path.join(fte_dir, "id1"), exist_ok=True)
    exe = extract.find_fte_exe(fte_dir, FTE_EXE_BY_PLATFORM[platform])
    if not exe:
        raise ClientError("No FTE client executable found in %s" % fte_dir)
    if not exe.lower().endswith(".exe"):
        for n in os.listdir(fte_dir):
            if n.startswith("fteq") and "." not in n:
                extract.mark_executable(os.path.join(fte_dir, n))
    for s in skipped:
        log("  kept your %s" % s)
    return exe, _copy_listing(root)
