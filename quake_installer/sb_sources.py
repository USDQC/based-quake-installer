"""unezQuake / ezQuake server browser sources: {unez}/ezquake/sb/sources.txt.

Format (parsed by Reload_Sources() in ezQuake's EX_browser_sources.c):
    <master|url|file> "<Name>" <address>
Lines starting with '/' are comments. 'master' is a QW master (host:port, UDP "c\\n\\0"),
'url' must return plain-text ip:port lines (fetched with curl), 'file' is sb/<file>.

unezQuake's release zips ship no sources.txt at all, so without this file the server
browser has nothing to refresh. The list below was verified live on 2026-10-18 (each
master answered a real master query with 300-600+ servers; the URL returned ~630
ip:port lines). Known-dead entries are listed in DEAD_SOURCES for reference only.

Merging: entries already in the user's file are kept verbatim (name and all);
duplicate entries (same type + address, case-insensitive; http/https treated alike
for urls) are dropped; missing defaults are appended. A changed file is backed up
once to sources.txt.bak; an unchanged file is not rewritten.
"""

import os
import re
import shutil

SOURCES_REL = os.path.join("ezquake", "sb", "sources.txt")

# (type, name, address) -- names are what sb_sourcemark matches (exact, case-sensitive).
DEFAULT_SOURCES = (
    ("master", "QuakeServers.net", "master.quakeservers.net:27000"),
    ("master", "Asgaard", "qwmaster.fodquake.net:27000"),
    ("master", "QuakeWorld.nu", "master.quakeworld.nu:27000"),
    ("url", "QuakeServers URL", "https://www.quakeservers.net/lists/servers/global.txt"),
)

# Checked 2026-10-18, not written. Reason in the value.
DEAD_SOURCES = {
    "217.153.59.106:27000": "ezQuake default 'Poland': master query times out",
    "qwmaster.ocrana.de:27000": "no DNS record",
    "netdome.biz:27000": "UDP port closed (ICMP refused)",
    "qwmaster.qw-dev.net:27000": "UDP port closed (ICMP refused)",
    "kubus.rulez.pl:27000": "master query times out",
    "qwmaster.mvdsv.com:27000": "no DNS record",
    "master.qwtf.live:27000": "no DNS record",
    "qwmaster.quakeworld.nu:27000": "no DNS record",
    "satan.idsoftware.com:27000": "no DNS record",
}

HEADER = ("// Server browser sources -- managed by Based Quake Installer.\n"
          "// Format: <master|url|file> \"<Name>\" <address>. Your own entries are kept on\n"
          "// reinstall/update; missing defaults are appended. Previous copy: sources.txt.bak\n")
ADDED_MARK = "// --- added by Based Quake Installer ---"

_LINE_RE = re.compile(r'^\s*(\S+)\s+(?:"([^"]*)"|(\S+))\s+(\S+)')


def parse_line(line):
    """(type, name, address) for a source line, else None (comment/blank/garbage).
    Mirrors ezQuake: first word must be master/file/url."""
    s = line.strip()
    if not s or s.startswith("/"):
        return None
    m = _LINE_RE.match(s)
    if not m:
        return None
    typ = m.group(1).lower()
    if typ not in ("master", "url", "file"):
        return None
    name = m.group(2) if m.group(2) is not None else m.group(3)
    return typ, name, m.group(4)


def _key(typ, address):
    a = address.strip().lower().rstrip("/")
    if typ == "url":
        a = re.sub(r"^https?://", "", a)
    return typ, a


def merge(existing_text, defaults=DEFAULT_SOURCES):
    """Return the merged sources.txt text (\\n line endings)."""
    out, seen_keys, seen_names = [], set(), set()
    lines = (existing_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line in lines:
        ent = parse_line(line)
        if ent is None:
            out.append(line.rstrip())
            continue
        k = _key(ent[0], ent[2])
        if k in seen_keys:
            continue  # duplicate entry
        seen_keys.add(k)
        seen_names.add(ent[1])
        out.append(line.rstrip())
    while out and out[-1] == "":
        out.pop()
    if not any(l.strip() for l in out):
        out = HEADER.rstrip("\n").split("\n")
    missing = [d for d in defaults
               if _key(d[0], d[2]) not in seen_keys and d[1] not in seen_names]
    if missing:
        if ADDED_MARK not in out:
            out.append(ADDED_MARK)
        for typ, name, addr in missing:
            out.append('%s "%s" %s' % (typ, name, addr))
    return "\n".join(out) + "\n"


def write_sources(unez_dir, log=print):
    """Create/merge {unez_dir}/ezquake/sb/sources.txt. Returns the path."""
    path = os.path.join(unez_dir, SOURCES_REL)
    old = None
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            old = fh.read().decode("utf-8", "replace")
    new = merge(old)
    if old is not None and old.replace("\r\n", "\n") == new:
        log("  server browser sources unchanged: %s" % path)
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if old is not None:
        shutil.copy2(path, path + ".bak")
        log("  backed up existing sources.txt -> %s" % (path + ".bak"))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    n = sum(1 for l in new.split("\n") if parse_line(l))
    log("  wrote %s (%d server browser sources)" % (path, n))
    for l in new.split("\n"):
        ent = parse_line(l)
        if ent and ent[2].lower() in DEAD_SOURCES:
            log("  NOTE: source %r (%s) looks dead: %s" % (ent[1], ent[2], DEAD_SOURCES[ent[2].lower()]))
    return path


def sourcemark_lines(defaults=DEFAULT_SOURCES):
    """based.cfg lines that tick our sources (ezQuake only auto-ticks a few fixed names)."""
    return ["sb_sourcemark \"%s\"" % name for _t, name, _a in defaults]
