"""Install manifest ({root}/based-quake-manifest.json) and update comparison logic.

Pure functions (no network) so they can be unit tested; the network side lives in
updater.py and passes plain dicts in.
"""

import json
import os
import time

from .constants import FTE_DIRNAME, UNEZ_DIRNAME

MANIFEST_NAME = "based-quake-manifest.json"
SCHEMA = 1

STATUS_OK = "up to date"
STATUS_OUTDATED = "update available"
STATUS_MISSING = "not installed"
STATUS_UNAVAILABLE = "no build for this platform"
STATUS_ERROR = "check failed"
STATUS_PLATFORM = "other platform"


def path_for(root):
    return os.path.join(root, MANIFEST_NAME)


def empty(platform=None):
    return {"schema": SCHEMA, "platform": platform, "components": {}}


def load(root):
    p = path_for(root)
    if not os.path.isfile(p):
        return empty()
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("components"), dict):
            return empty()
        return data
    except (OSError, ValueError):
        return empty()


def save(root, data):
    os.makedirs(root, exist_ok=True)
    p = path_for(root)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, p)
    return p


def record(data, component, remote, files=None, platform=None, extra=None):
    """Store what was just installed for ``component`` (remote = meta dict)."""
    entry = {
        "version": remote.get("version"),
        "url": remote.get("url"),
        "size": remote.get("size"),
        "etag": remote.get("etag"),
        "last_modified": remote.get("last_modified"),
        "sha256": remote.get("sha256"),
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if platform:
        entry["platform"] = platform
    if files is not None:
        entry["files"] = list(files)
    if remote.get("steps") is not None:
        entry["steps"] = remote["steps"]
    if extra:
        entry.update(extra)
    data.setdefault("components", {})[component] = entry
    return entry


def _etag(e):
    e = e.strip()
    if e.startswith("W/"):
        e = e[2:]
    return e.strip('"')


def _same_file(a, b):
    """Compare two single-file metas. Prefer version tag, then ETag, then size+date."""
    if a.get("version") and b.get("version"):
        return a["version"] == b["version"]
    if a.get("etag") and b.get("etag"):
        return _etag(a["etag"]) == _etag(b["etag"])
    if a.get("size") is not None and b.get("size") is not None and a["size"] != b["size"]:
        return False
    if a.get("last_modified") and b.get("last_modified"):
        return a["last_modified"] == b["last_modified"]
    if a.get("size") is not None and b.get("size") is not None:
        return a["size"] == b["size"]
    return True  # nothing comparable: don't invent an update


def compare(installed, remote, platform=None):
    """Return a status string for one component.

    installed: manifest entry or None. remote: meta dict, None (no build), or
    {"error": msg}. Multi-file mods carry "steps" lists compared pairwise by file.
    """
    if remote is None:
        return STATUS_UNAVAILABLE
    if remote.get("error"):
        return STATUS_ERROR
    if installed is None:
        return STATUS_MISSING
    if platform and installed.get("platform") and installed["platform"] != platform:
        return STATUS_OUTDATED
    if remote.get("sha256"):
        # Drive mod zip: sha256 (and version, when both have one) must match. A mod
        # installed from the old mirrors has no sha256 -> offer the Drive zip once.
        if (installed.get("sha256") or "").lower() != remote["sha256"].lower():
            return STATUS_OUTDATED
        if installed.get("version") and remote.get("version") and \
                str(installed["version"]) != str(remote["version"]):
            return STATUS_OUTDATED
        return STATUS_OK
    if remote.get("steps") is not None:
        have = {s.get("file", "").lower(): s for s in (installed.get("steps") or [])}
        for step in remote["steps"]:
            mine = have.get(step.get("file", "").lower())
            if mine is None:
                # No record for this file (pre-1.6 install): fall back to spec size.
                if step.get("spec_size") is not None and step.get("size") is not None \
                        and step["spec_size"] != step["size"]:
                    return STATUS_OUTDATED
                continue
            if not _same_file(mine, step):
                return STATUS_OUTDATED
        return STATUS_OK
    return STATUS_OK if _same_file(installed, remote) else STATUS_OUTDATED


ENGINE_KEYS = ("unez", "fte")


def record_engines(data, opts):
    """Remember which engines a full install uses and the folders they live in.

    An engine that is turned off keeps the folder recorded by an earlier install,
    so the updater can still tell that it is there."""
    dirs = data.get("engine_dirs") if isinstance(data.get("engine_dirs"), dict) else {}
    dirs = dict(dirs)
    selected = {}
    for key, on, path in (("unez", opts.install_unez, opts.unez_dir),
                          ("fte", opts.install_fte, opts.fte_dir)):
        selected[key] = bool(on)
        if on and path:
            dirs[key] = os.path.abspath(path)
    data["engine_dirs"] = dirs
    data["engines_selected"] = selected
    return data


def engine_dirs(data):
    """{"unez": path, "fte": path} recorded by record_engines(); {} for old manifests."""
    dirs = data.get("engine_dirs") if isinstance(data, dict) else None
    if not isinstance(dirs, dict):
        return {}
    return {k: dirs[k] for k in ENGINE_KEYS if isinstance(dirs.get(k), str) and dirs[k]}


def engine_folders(data, root):
    """Recorded engine folders, falling back to the default under root when an
    old manifest only lists the engine component."""
    dirs = engine_dirs(data)
    comps = data.get("components", {}) if isinstance(data, dict) else {}
    for key, dirname in (("unez", UNEZ_DIRNAME), ("fte", FTE_DIRNAME)):
        if not dirs.get(key) and ("client:" + key) in comps:
            dirs[key] = os.path.join(root, dirname)
    return dirs
