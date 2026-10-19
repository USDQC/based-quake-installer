"""Mods installed as separate gamedirs under each declared client tree
({root}/FTE/<gamedir>, {root}/unezQuake/<gamedir>).

Every mod downloads ONLY from the maintainer's Google Drive: one pre-processed
<gamedir>.zip per mod (already merged/patched, nested archives unpacked, names
lowercase; top-level folder = gamedir). The old idgames/ModDB/fvfonline mirrors and
the per-mod .7z/.lha handling are gone.

Where the links come from, in order:
  1. a mods.json index on Drive (MODS_INDEX_URL, one stable link; per mod: gamedir,
     version, sha256, size, clients, url),
  2. a mods.json next to installer_gui.py / the .exe (same format, or the older list
     of overrides), else
  3. the built-in table below (version/sha256/size of the zips as built 2026-10-18).
Each zip's size and sha256 are verified before anything is unpacked.
"""

import json
import os
import shutil

from . import download, drive, extract
from .constants import MODS_INDEX_URL
from .paths import exe_side_path

PLACEHOLDER = "PASTE_DRIVE_LINK"

MODS = [
    {"key": "airquake", "clients": ["fte"], "title": "AirQuake 1.03", "gamedir": "airquake",
     "version": "1.03", "built_from": ["airq102.zip", "airq103p.zip"],
     "needs_registered": False,
     "note": "Total conversion with its own maps and its own autoexec/config."},
    {"key": "painkeep", "clients": ["fte", "unez"], "title": "PainKeep 1.11",
     "gamedir": "painkeep", "version": "1.11", "built_from": ["PK111NWN.ZIP"],
     "needs_registered": True,
     "note": "Deathmatch mission pack; best with registered Quake (pak1.pak in each client's id1)."},
    {"key": "hh", "clients": ["fte", "unez"], "title": "Headhunters 3.0 (client pak)",
     "gamedir": "hh", "version": "3.0", "built_from": ["hh30cl.zip"],
     "needs_registered": True,
     "note": "Multiplayer mod; uses deathmatch content from registered Quake."},
    {"key": "fortress", "clients": ["fte", "unez"], "title": "Team Fortress 2.8 + 2.9 QW",
     "gamedir": "fortress", "version": "2.8+2.9qw", "built_from": ["tf28.zip", "tf29qw.zip"],
     "needs_registered": True,
     "note": "Classic QuakeWorld Team Fortress. Launch either client with -game fortress."},
    {"key": "thunderwalker", "clients": ["fte", "unez"],
     "title": "Thunderwalker CTF (ThreeWave + TW 3.01)", "gamedir": "ctf",
     "version": "3wctfc+tw3.01", "built_from": ["3wctfc.zip", "tw301_cl.zip"],
     "needs_registered": True,
     "note": "ThreeWave CTF base + Thunderwalker 3.01 client into ctf/ (both clients). "
             "Launch either client with -game ctf."},
    {"key": "arena", "clients": ["fte", "unez"], "title": "Rocket Arena (Final Arena 1.2)",
     "gamedir": "arena", "version": "1.2", "built_from": ["farena12.zip"],
     "needs_registered": False,
     "note": "Final Arena 1.2 client pack (maps/sounds) into arena/. Launch with -game arena."},
    {"key": "fvf", "clients": ["fte"], "title": "Future vs Fantasy 4", "gamedir": "fvf",
     "version": "4+clientpak2.09.21", "built_from": ["fvf4.zip", "FvFclientPak20921.7z"],
     "needs_registered": True,
     "note": "Future vs Fantasy 4 + client pak 2.09.21 into FTE/fvf. Launch FTE with -game fvf."},
    {"key": "rally", "clients": ["fte"], "title": "Quake Rally", "gamedir": "rally",
     "version": "1.2+lo1", "built_from": ["qr12.zip", "qrlo1.zip"],
     "needs_registered": True,
     "note": "Quake Rally 1.2 + Leftovers into FTE/rally. Launch FTE with -game rally. "
             "Needs registered Quake (pak1.pak)."},
    {"key": "grq", "clients": ["fte", "unez"], "title": "Get Rich Quake 1.1", "gamedir": "grq",
     "version": "1.1", "built_from": ["grqcl_11.zip", "grqsv11a.zip"],
     "needs_registered": True,
     "note": "Mod Damage deathmatch money mod (NQ progs.dat + QW qwprogs.dat). "
             "Launch with -game grq; played on registered DM maps."},
    {"key": "runequake", "clients": ["fte", "unez"], "title": "Rune Quake",
     "gamedir": "runequake",
     # Server-side mod: nothing to download. The installer only creates the
     # gamedir with binds.cfg + autoexec.cfg (exec binds.cfg) for the Mod binds tab.
     "binds_only": True, "needs_registered": False,
     "note": "Server-side rune DM mod; only binds are set up. Join a Rune Quake "
             "server with -game runequake."},
]

# Drive zips as built by packaging/drive/build_drive_zips.py (filled in below).
DRIVE_FILES = {
    "airquake": {"sha256": "2b3d9903cf6a39dd9c388495cd0832eb2600d75b2d700dbff7227fd2e65623e1",
                "size": 4559986,
                "url": "https://drive.google.com/file/d/1OxnDljyGGmN14yLfPbJeNtQLjhtNN0Kr/view"},
    "painkeep": {"sha256": "e2cccacfe23927ce650d4bfc4fc27400d9849d8689e41a0ba67528bc49a58f91",
                "size": 13277699,
                "url": "https://drive.google.com/file/d/1X0FmbL_ZfzhduQnDuQFvtB7t6wpzFnIb/view"},
    "hh": {"sha256": "d72ab483d00fcd086d0fbbcb6c99ab08479d8043847ddbf0c6d691a786d0a3de",
          "size": 5538546,
          "url": "https://drive.google.com/file/d/10xgdahOVbr38HSiqJlCUNH9JsGER1MRw/view"},
    "fortress": {"sha256": "8e4118ddaa7f9178cb3b3255ac2df33c590d35c2f093ecca1756b9bfa3b1a3e7",
                "size": 4169491,
                "url": "https://drive.google.com/file/d/1objpFOB8rGS-RqieMaODK-aBIX9JCEiY/view"},
    "thunderwalker": {"sha256": "c0b5938acf78204eb921eca80c37aa0b588cd2923664f55292e0bae475464e39",
                     "size": 17419183,
                     "url": "https://drive.google.com/file/d/1gRZ_4amMnatU88AABU8pSA7hFG43r7ia/view"},
    "arena": {"sha256": "220fff57e6a13a5dcaede0838b445e06093287f45d9e69faa28d452de3822304",
             "size": 6956678,
             "url": "https://drive.google.com/file/d/1CXuyN3lUu6VYct6FocaLYpSpbA5LwRME/view"},
    "fvf": {"sha256": "2fdc26dfcc4ab1f1710a9330b747d7e5cf061f55e72b347bc16ab1fa583a6f50",
           "size": 7467292,
           "url": "https://drive.google.com/file/d/1bpsQ5240CW2jrhu0EVm2UpVDI2kvEmJv/view"},
    "rally": {"sha256": "ba6bd245c7ad2b77fb3f6e7019601378eff039a5a13278c6a28851714e459456",
             "size": 13626962,
             "url": "https://drive.google.com/file/d/1z8USnmQZOveOFuW2tgGW3A_61-E6-LYf/view"},
    "grq": {"sha256": "0f09e1f88c195032b1a1083dc74cdab0cb50210589b4b74b27513270552e4221",
           "size": 632122,
           "url": "https://drive.google.com/file/d/1Q5R07Oozd0VtWS1_mlTlcrQnyNbKP7M4/view"},
}
for _m in MODS:
    if not _m.get("binds_only"):
        _m.update({"file": _m["gamedir"] + ".zip", "url": PLACEHOLDER})
        _m.update(DRIVE_FILES.get(_m["key"], {}))


class ModError(Exception):
    pass


# Fields a mods.json entry may set on a built-in mod.
INDEX_FIELDS = ("title", "gamedir", "version", "sha256", "size", "clients", "url", "file",
                "note", "needs_registered")


def index_entries(data):
    """Entries from a mods.json: {"format": 1, "mods": [...]} or a bare list."""
    if isinstance(data, dict):
        data = data.get("mods", [])
    if not isinstance(data, list):
        raise ValueError("mods.json: expected a list of mods")
    return [e for e in data if isinstance(e, dict) and e.get("key")]


def apply_index(specs, data):
    """Overlay mods.json entries onto specs (in place). Unknown keys become new mods
    when they carry at least title/gamedir/url."""
    by_key = {m["key"]: m for m in specs}
    for e in index_entries(data):
        # A placeholder / empty value never replaces a real one (e.g. a mods.json on
        # Drive that still says "url": "PASTE_DRIVE_LINK" keeps the built-in link).
        e = {k: v for k, v in e.items()
             if not (isinstance(v, str) and v.strip() in ("", PLACEHOLDER)) and v is not None}
        if "key" not in e:
            continue
        if e["key"] in by_key:
            by_key[e["key"]].update({k: v for k, v in e.items() if k in INDEX_FIELDS})
        elif e.get("gamedir") and e.get("url"):
            new = dict(e)
            new.setdefault("title", e["key"])
            new.setdefault("file", e["gamedir"] + ".zip")
            specs.append(new)
            by_key[e["key"]] = new
    return specs


def index_url():
    """The one stable Drive link to mods.json, or None while it is still a placeholder.
    BASED_QUAKE_MODS_INDEX (env) overrides it (testing / a self-hosted mirror)."""
    url = (os.environ.get("BASED_QUAKE_MODS_INDEX") or MODS_INDEX_URL or "").strip()
    return url if url and url != PLACEHOLDER else None


def fetch_index(url=None, get_text=None):
    """Download and parse mods.json. Raises download.DownloadError / ValueError."""
    url = url or index_url()
    if not url:
        return None
    text = (get_text or drive.get_text)(url)
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError("mods.json from %s is not valid JSON (%s)" % (url, exc))
    index_entries(data)  # validate shape
    return data


def load_specs(index=None):
    """Built-in table, then a local mods.json next to the exe, then the Drive index."""
    specs = [dict(m) for m in MODS]
    path = exe_side_path("mods.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                apply_index(specs, json.load(fh))
        except Exception as exc:  # bad json shouldn't kill the installer
            print("mods.json ignored: %s" % exc)
    if index is not None:
        apply_index(specs, index)
    return specs


def load_specs_online(log=print, get_text=None):
    """load_specs() with the Drive index when one is configured and reachable.
    Returns (specs, error_or_None); falls back to the built-in table on error."""
    url = index_url()
    if not url:
        return load_specs(), None
    try:
        return load_specs(fetch_index(url, get_text=get_text)), None
    except (download.DownloadError, ValueError) as exc:
        log("  WARN: could not read mods.json from Drive (%s); using built-in mod list"
            % str(exc).split("\n")[0])
        return load_specs(), str(exc)


def _has_game_files(folder):
    try:
        names = [n.lower() for n in os.listdir(folder)]
    except OSError:
        return False
    return any(n in ("progs.dat", "qwprogs.dat", "csprogs.dat", "pak0.pak", "pak1.pak",
                     "pak2.pak") or
               n.endswith((".pk3", ".pak")) or n == "maps" for n in names)


def client_dirs(spec, fte_dir, unez_dir):
    """Return [(label, target_dir), ...] for this mod's declared clients."""
    gamedir = spec["gamedir"]
    clients = spec.get("clients") or ["fte"]
    out = []
    for c in clients:
        if c == "fte":
            out.append(("FTE", os.path.join(fte_dir, gamedir)))
        elif c == "unez":
            out.append(("unezQuake", os.path.join(unez_dir, gamedir)))
    return out


def _install_binds_only(spec, targets, log):
    """Server-side mods: create {client}/{gamedir}/ with binds.cfg + autoexec.cfg only."""
    from . import binds_mods
    for label, target in targets:
        os.makedirs(target, exist_ok=True)
        binds_path = os.path.join(target, "binds.cfg")
        if not os.path.isfile(binds_path):
            text = binds_mods.render_mod_binds_cfg(spec["key"], {}, title=spec.get("title"))
            with open(binds_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        binds_mods.merge_mod_autoexec(target)
        binds_mods.ensure_switch_hook(target, label)
        log("  OK: %s -> %s (%s, binds only; server-side mod)" % (spec["title"], target, label))
    return "binds only (server-side mod)"


def verify_zip(spec, path):
    """Size + sha256 against the mods.json / built-in values. Raises ModError."""
    size = os.path.getsize(path)
    if spec.get("size") is not None and size != int(spec["size"]):
        raise ModError("%s: %s is %d bytes, expected %d (wrong or partial file)"
                       % (spec["title"], spec.get("file"), size, int(spec["size"])))
    want = (spec.get("sha256") or "").lower()
    if not want:
        raise ModError("%s: no sha256 in mods.json; refusing to install unverified zip"
                       % spec["title"])
    got = extract.file_sha256(path)
    if got != want:
        raise ModError("%s: sha256 mismatch for %s\n    got      %s\n    expected %s\n"
                       "    (the Drive file changed without mods.json being updated, or "
                       "the download is corrupt). Nothing was installed."
                       % (spec["title"], spec.get("file"), got, want))
    return got


def _payload_dir(stage, gamedir):
    for n in os.listdir(stage):
        p = os.path.join(stage, n)
        if n.lower() == gamedir.lower() and os.path.isdir(p):
            return p
    raise ModError("zip has no top-level %s/ folder (got: %s)"
                   % (gamedir, ", ".join(sorted(os.listdir(stage))[:5]) or "empty"))


def install_mod(spec, fte_dir, work_dir, progress=None, cancel_event=None, log=print,
                local_file=None, unez_dir=None, meta_out=None, protect=(),
                fetch=None):
    """Download <gamedir>.zip from Drive, verify it, unzip into each declared client
    tree. local_file: an already downloaded copy of that same zip (still verified).
    meta_out (dict) receives {file,url,version,sha256,size}. Returns a source desc."""
    gamedir = spec["gamedir"]
    targets = client_dirs(spec, fte_dir, unez_dir or fte_dir)
    if not targets:
        raise ModError("%s: no client trees declared" % spec["title"])
    if spec.get("binds_only"):
        return _install_binds_only(spec, targets, log)
    stage_base = os.path.join(work_dir, "mod-" + spec["key"])
    shutil.rmtree(stage_base, ignore_errors=True)
    os.makedirs(stage_base)
    fname = spec.get("file") or gamedir + ".zip"
    url = (spec.get("url") or "").strip()
    if local_file:
        if not os.path.isfile(local_file):
            raise ModError("%s: local file not found: %s" % (spec["title"], local_file))
        zpath, source = local_file, "local file %s" % os.path.basename(local_file)
        log("  using local %s" % local_file)
    else:
        if not url or url == PLACEHOLDER:
            raise ModError("%s: no Google Drive link configured yet (mods.json url is %s)"
                           % (spec["title"], url or "empty"))
        zpath = os.path.join(stage_base, fname)
        log("  downloading %s from %s" % (fname, drive.describe(url)))
        (fetch or drive.download)(url, zpath, progress=progress, cancel_event=cancel_event,
                                  log=log)
        source = "Google Drive (%s %s)" % (fname, spec.get("version") or "")
    sha = verify_zip(spec, zpath)
    log("  OK: sha256 verified (%s...)" % sha[:16])
    stage = os.path.join(stage_base, "x")
    try:
        extract.safe_extract_zip(zpath, stage)
    except Exception as exc:
        raise ModError("%s: %s is not a valid zip (%s)" % (spec["title"], fname, exc))
    payload = _payload_dir(stage, gamedir)
    extract.lowercase_tree(payload, incoming_wins=True)  # defensive; zips are lowercase
    if not _has_game_files(payload):
        raise ModError("%s: no progs.dat / pak files in %s" % (spec["title"], fname))
    for label, target in targets:
        os.makedirs(target, exist_ok=True)
        extract.copy_tree_over(payload, target, protect=protect)
        # Old installs (<=1.6.1) left PAK0.PAK / GFX/ etc.; the fresh lowercase copy wins.
        extract.lowercase_tree(target, incoming_wins=False, log=log)
        if not _has_game_files(target):
            raise ModError("%s: no game files ended up in %s" % (spec["title"], target))
        log("  OK: %s -> %s (%s)" % (spec["title"], target, label))
    if meta_out is not None:
        meta_out.update({"file": fname, "url": None if local_file else url,
                         "version": spec.get("version"), "sha256": sha,
                         "size": os.path.getsize(zpath)})
    shutil.rmtree(stage, ignore_errors=True)
    return source
