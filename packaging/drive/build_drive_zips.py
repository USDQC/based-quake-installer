#!/usr/bin/env python3
"""Build the Google Drive upload set: one <gamedir>.zip per mod plus mods.json.

Usage:
    build_drive_zips.py <staged_root> <out_dir> [--version key=VER ...]

<staged_root>/<gamedir>/ must hold each mod's FINAL gamedir contents (already merged,
patched, nested archives unpacked, names lowercase). Installer-generated files
(our merged autoexec.cfg, binds.cfg) must not be in there; this script refuses them.

Packs (skins, sprays): <staged_root>/<key>/ holds the folder contents (e.g.
skins/*.pcx); the zip is <key>.zip with top-level folder qw/ (the pack's gamedir).

--only KEY (repeatable) builds just those; every other entry of an existing
out_dir/mods.json is kept unchanged (sha256/size/url).

Zips are deterministic (sorted entries, fixed timestamp, deflate 9), so rezipping
unchanged content gives the same sha256. mods.json "url" fields are left as
PASTE_DRIVE_LINK (or kept from an existing out_dir/mods.json).
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from quake_installer import mods as modlib  # noqa: E402
from quake_installer.binds_mods import EXEC_LINE, BASED_LINE  # noqa: E402

FIXED_TS = (2026, 10, 18, 0, 0, 0)
PLACEHOLDER = "PASTE_DRIVE_LINK"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_clean_pack(pdir, spec):
    problems = []
    for root, _d, files in os.walk(pdir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), pdir).replace(os.sep, "/")
            if rel != rel.lower():
                problems.append("uppercase name: " + rel)
            if os.path.dirname(rel) != spec["subdir"]:
                problems.append("outside %s/: %s" % (spec["subdir"], rel))
            if not f.endswith(modlib.PACK_EXTS):
                problems.append("not an image: " + rel)
    return problems


def check_clean(gdir):
    problems = []
    for root, _d, files in os.walk(gdir):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, gdir)
            if rel != rel.lower():
                problems.append("uppercase name: " + rel)
            if f == "binds.cfg" and root == gdir:
                problems.append("installer-generated binds.cfg")
            if f == "autoexec.cfg" and root == gdir:
                txt = open(p, "r", encoding="utf-8", errors="replace").read().lower()
                if BASED_LINE in txt or EXEC_LINE in txt:
                    problems.append("autoexec.cfg already merged by the installer")
            if f.endswith((".lha", ".lzh", ".7z", ".rar")):
                problems.append("nested archive left: " + rel)
    return problems


def make_zip(gdir, gamedir, out_path):
    entries = []
    for root, dirs, files in os.walk(gdir):
        dirs.sort()
        rel_root = os.path.relpath(root, gdir).replace(os.sep, "/")
        prefix = gamedir + "/" + ("" if rel_root == "." else rel_root + "/")
        entries.append((prefix, None))
        for f in sorted(files):
            entries.append((prefix + f, os.path.join(root, f)))
    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, src in sorted(entries):
            zi = zipfile.ZipInfo(name, FIXED_TS)
            if src is None:
                zi.external_attr = (0o40755 << 16) | 0x10
                zf.writestr(zi, b"")
            else:
                zi.external_attr = 0o100644 << 16
                zi.compress_type = zipfile.ZIP_DEFLATED
                with open(src, "rb") as fh:
                    zf.writestr(zi, fh.read(), compresslevel=9)
    os.replace(tmp, out_path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("staged_root")
    ap.add_argument("out_dir")
    ap.add_argument("--version", action="append", default=[], metavar="KEY=VER")
    ap.add_argument("--only", action="append", default=[], metavar="KEY")
    a = ap.parse_args(argv)
    versions = dict(v.split("=", 1) for v in a.version)
    os.makedirs(a.out_dir, exist_ok=True)
    idx_path = os.path.join(a.out_dir, "mods.json")
    old_urls, old_entries = {}, {}
    if os.path.isfile(idx_path):
        for m in json.load(open(idx_path)).get("mods", []):
            old_urls[m["key"]] = m.get("url", PLACEHOLDER)
            old_entries[m["key"]] = m
    out, failed = [], False
    for spec in modlib.MODS:
        if spec.get("binds_only"):
            continue
        if a.only and spec["key"] not in a.only:
            if spec["key"] in old_entries:
                out.append(old_entries[spec["key"]])
            else:
                print("NOTE: %s not built and not in the old mods.json" % spec["key"])
            continue
        gd = spec["gamedir"]
        pack = modlib.is_pack(spec)
        gdir = os.path.join(a.staged_root, spec["key"] if pack else gd)
        if not os.path.isdir(gdir):
            print("MISSING staged dir: %s" % gdir)
            failed = True
            continue
        probs = check_clean_pack(gdir, spec) if pack else check_clean(gdir)
        if probs:
            print("%s: not clean:\n  %s" % (gd, "\n  ".join(probs[:10])))
            failed = True
            continue
        fname = spec["file"]
        zpath = os.path.join(a.out_dir, fname)
        make_zip(gdir, gd, zpath)
        nfiles = sum(len(f) for _r, _d, f in os.walk(gdir))
        extra = {"kind": "pack", "subdir": spec["subdir"]} if pack else {}
        out.append(dict({
            "key": spec["key"], "title": spec["title"], "gamedir": gd,
            "file": fname,
            "version": versions.get(spec["key"], spec.get("version", "1")),
            "sha256": sha256(zpath), "size": os.path.getsize(zpath),
            "files": nfiles, "clients": list(spec.get("clients") or ["fte"]),
            "url": old_urls.get(spec["key"], PLACEHOLDER),
        }, **extra))
        print("%-12s %10d bytes  %s" % (fname, out[-1]["size"], out[-1]["sha256"]))
    index = {"format": 1, "name": "Based Quake Installer mods", "mods": out}
    with open(idx_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, indent=2)
        fh.write("\n")
    print("wrote %s (%d mods)" % (idx_path, len(out)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
