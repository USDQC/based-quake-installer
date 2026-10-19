"""Per-mod bindable actions discovered from archives / docs (not invented).

Shared vanilla QW+weapons binds still write to each engine tree's id1 autoexec.
These optional mod binds write into {client}/{gamedir}/binds.cfg and ensure
that gamedir's autoexec.cfg execs binds.cfg — only for mods listed here.

Sources are recorded in MOD-BIND-REPORT.md.
"""

# Each entry: (action_id, quake_command, UI_label)
# Only mods with clear, grounded custom binds appear here.

MOD_BIND_ACTIONS = {
    # Team Fortress 2.8/2.9 — fortress/README.TXT Command + Impulse Summary
    "fortress": [
        ("gren1", "+gren1", "Grenade type 1 (+gren1)"),
        ("gren2", "+gren2", "Grenade type 2 (+gren2)"),
        ("special", "special", "Class special"),
        ("reload", "reload", "Reload"),
        ("detpipe", "detpipe", "Detonate pipebombs"),
        ("hook", "impulse 22", "Select hook"),
        ("hook39", "impulse 39", "Select hook (alt: impulse 39)"),
        ("axe", "impulse 40", "Select axe"),
        ("lastweapon", "impulse 69", "Last weapon"),
        ("inv", "inv", "Inventory"),
        ("flaginfo", "flaginfo", "Flag info"),
        ("discard", "discard", "Discard unused ammo"),
        ("saveme", "saveme", "Call for medic/repair"),
        ("dropammo", "dropammo", "Drop ammo"),
        ("changeclass", "changeclass", "Class menu"),
    ],
    # Thunderwalker CTF / ThreeWave — twdocs/impulses.htm + Threewave wiki
    "thunderwalker": [
        ("q_airfist", "+bqi_airfist", "Quick AirFist (fire, switch back)"),
        ("q_hook", "+bqi_hook", "Quick grappling hook (hold, switch back)"),
        ("hook", "impulse 22", "Grappling hook"),
        ("throwammo", "impulse 20", "Throw ammo backpack"),
        ("throwweapon", "impulse 21", "Throw current weapon"),
        ("flagstatus", "impulse 23", "Flag status"),
        ("airfist", "impulse 47", "AirFist"),
        ("lastweapon", "impulse 69", "Previous weapon"),
        ("flare", "impulse 160", "Fire flare"),
        ("runeinfo", "impulse 180", "Rune info"),
        ("droprune", "impulse 181", "Destroy/drop rune"),
        ("teleport", "impulse 200", "Personal teleporter"),
        ("idtarget", "impulse 141", "ID target"),
    ],
    # Rocket Arena / Final Arena 1.2 — farena12 readme.txt Impulse Quick Reference
    "arena": [
        ("stats", "impulse 68", "Arena stats"),
        ("position", "impulse 69", "Line position"),
        ("break", "impulse 70", "Take break / return"),
        ("sbar200", "impulse 71", "Status bar 320x200"),
        ("sbar240", "impulse 72", "Status bar 320x240+"),
    ],
    # PainKeep — IMPULSES.TXT (optional direct selects; 1–8 still work via vanilla)
    "painkeep": [
        ("q_airfist", "+bqi_airfist", "Quick AirFist (fire, switch back)"),
        ("q_gravitywell", "+bqi_gravitywell", "Quick Gravity Well (drop, back)"),
        ("q_beartrap", "+bqi_beartrap", "Quick bear trap (drop, back)"),
        ("q_autosentry", "+bqi_autosentry", "Quick AutoSentry (drop, back)"),
        ("q_beans", "+bqi_beans", "Quick Pork & Beans (use, back)"),
        ("grapple", "impulse 21", "Grapple / harpoon"),
        ("airfist", "impulse 30", "AirFist"),
        ("chainlg", "impulse 32", "Chain lightning"),
        ("gravitywell", "impulse 33", "Gravity Well"),
        ("beartrap", "impulse 34", "Bear trap"),
        ("autosentry", "impulse 35", "AutoSentry"),
        ("beans", "impulse 36", "Pork & Beans"),
        ("invstats", "impulse 38", "Inventory stats"),
        ("releasehook", "impulse 50", "Release harpoon"),
        ("lastweapon", "impulse 69", "Previous weapon"),
    ],
    # AirQuake — AUTOEXEC.CFG + AQALIAS.CFG (FTE-only)
    "airquake": [
        ("freelook", "+freelook", "Free look"),
        ("extraleft", "+extraleft", "Extra left / roll"),
        ("extraright", "+extraright", "Extra right / roll"),
        ("cczoomin", "+cczoomin", "Cockpit zoom in"),
        ("cczoomout", "+cczoomout", "Cockpit zoom out"),
        ("liftcam", "liftcam", "Lift camera"),
        ("lockturret", "lockturret", "Lock turret"),
        ("impulse9", "impulse 9", "Weapon / slot 9"),
    ],
    # Quake Rally — RALLY.CFG + QRDOCS.TXT (FTE-only)
    "rally": [
        ("accelerate", "+accelerate", "Accelerate"),
        ("reverse", "+reverse", "Reverse"),
        ("horn", "+horn", "Horn"),
        ("zoomin", "+zoomin", "Camera zoom in"),
        ("zoomout", "+zoomout", "Camera zoom out"),
        ("cameraview", "impulse 40", "Camera near/far"),
        ("incar", "impulse 43", "In-car view toggle"),
        ("headlights", "impulse 50", "Headlights"),
        ("obsfwd", "impulse 150", "Observer next"),
        ("obsback", "impulse 151", "Observer prev"),
        ("changecar", "impulse 201", "Change car"),
        ("sway_loose", "impulse 120", "Camera sway loose"),
        ("sway_tight", "impulse 130", "Camera sway tight"),
    ],
    # Get Rich Quake — Readme.txt COMMAND SUMMARY + gr_utils.qc GR_SetAliases/GR_ImpulseCommands
    "grq": [
        ("cashbox", "impulse 120", "Cashbox (drop/fill/status)"),
        ("hook", "impulse 22", "Grappling hook"),
        ("grq_scores", "impulse 121", "Team scores"),
    ],
    # Rune Quake — Playing ("Player Commands") + bindings.qc aliases / defs.qc IMP_*
    "runequake": [
        ("rune_use", "impulse 100", "Use rune (rune-use)"),
        ("rune_delete", "impulse 98", "Delete rune (rune-delete)"),
        ("rune_tell", "impulse 99", "Rune info (rune-tell)"),
        ("show_riders", "impulse 96", "Show riders"),
        ("fix_angles", "impulse 95", "Fix angles"),
        ("best_weapon", "impulse 92", "Best weapon"),
        ("weapon_mode", "impulse 86", "Weapon mode (alt weapon)"),
        ("hook", "+hook", "Grappling hook (hold)"),
        ("show_players", "impulse 97", "Show players"),
        ("observer", "impulse 201", "Observer menu"),
    ],
}

# Quick-use aliases: press = select the item and hold fire, release = stop firing and
# go back with the mod's own "previous weapon" impulse (69). The select impulse and
# +attack go out in the same client frame; the server runs ImpulseCommands before
# W_Attack in W_WeaponFrame, so the new weapon fires at once (no wait needed). The
# release impulse waits on the server until the shot's attack_finished has passed.
#
# PainKeep 1.11 (pk111src qwsrc): impulses 30/33/34/35/36 in pk_ChangeWeapon
# (weapons.qc:1851-1905), 69 = lastweapon (weapons.qc:2450-2459, tracked in
# W_SetCurrentAmmo weapons.qc:1285-1291), W_WeaponFrame weapons.qc:2581-2602.
# Thunderwalker 3.01 (tw301qsv twqwsrc): 47 = AirFist (defs.qc:810, weapons.qc:1527),
# 22 = grapple (weapons.qc:1479), 69 = PreviousWeaponCommand (weapons.qc:1849,1942);
# the hook drops when fire is released (grapple.qc:375-379) in PlayerPreThink
# (client.qc:1156), before the 69 runs in W_WeaponFrame (client.qc:1358).
_PREV = "impulse 69"
QUICK_ALIASES = {
    "painkeep": {
        "q_airfist": ("bqi_airfist", "impulse 30"),
        "q_gravitywell": ("bqi_gravitywell", "impulse 33"),
        "q_beartrap": ("bqi_beartrap", "impulse 34"),
        "q_autosentry": ("bqi_autosentry", "impulse 35"),
        "q_beans": ("bqi_beans", "impulse 36"),
    },
    "thunderwalker": {
        "q_airfist": ("bqi_airfist", "impulse 47"),
        "q_hook": ("bqi_hook", "impulse 22"),
    },
}


def quick_alias_lines(mod_key, action_id):
    """The two alias lines for one quick-use action, or [] if it isn't one."""
    entry = (QUICK_ALIASES.get(mod_key) or {}).get(action_id)
    if not entry:
        return []
    name, select = entry
    return ['alias +%s "%s; +attack"' % (name, select),
            'alias -%s "-attack; %s"' % (name, _PREV)]


# Mods researched with no useful extra bind UI (vanilla weapons enough / no impulses)
MOD_BIND_SKIP = {
    "hh": "Client pak readme documents Grapple Gun but no impulse/bind table in archive.",
    "fvf": "FvF4 readme: 'No Impulses to Bind / No Aliases to Learn'.",
}


def mods_with_bind_ui():
    """Mod keys that should show a Mod binds panel."""
    return [k for k, actions in MOD_BIND_ACTIONS.items() if actions]


def actions_for(mod_key):
    return list(MOD_BIND_ACTIONS.get(mod_key) or [])


def action_by_id(mod_key):
    return {a[0]: a for a in actions_for(mod_key)}


def clean_mod_binds(mod_key, binds):
    """Return {action_id: key} for one mod; blank/unknown skipped."""
    from . import cfg
    known = action_by_id(mod_key)
    out = {}
    for action_id, raw in (binds or {}).items():
        if action_id not in known:
            continue
        key = cfg.normalize_key(raw)
        if key:
            out[action_id] = key
    return out


def unknown_mod_bind_actions(mod_key, binds):
    """Action ids in binds that this mod doesn't offer (they are dropped)."""
    known = action_by_id(mod_key)
    return sorted(a for a, v in (binds or {}).items() if a not in known and str(v or "").strip())


def render_mod_binds_cfg(mod_key, binds, title=None):
    """Render binds.cfg text for one mod gamedir (no unbindall — additive)."""
    from . import cfg
    cleaned = clean_mod_binds(mod_key, binds)
    lines = [
        "// binds.cfg for -game %s — generated by Based Quake Installer" % mod_key,
        "// Only non-blank Mod binds fields; does not unbindall.",
        "",
    ]
    if title:
        lines[0] = "// binds.cfg for %s — generated by Based Quake Installer" % title
    if not cleaned:
        lines.append("// (no mod binds chosen)")
        lines.append("")
        return "\r\n".join(lines)
    seen = set()
    aliases, binds = [], []
    for action_id, cmd, _label in actions_for(mod_key):
        if action_id not in cleaned:
            continue
        key = cleaned[action_id]
        kl = key.lower()
        if kl in seen:
            continue
        seen.add(kl)
        aliases.extend(quick_alias_lines(mod_key, action_id))
        binds.append(cfg._fmt_bind(key, cmd))
    if aliases:
        lines.append("// Quick use: hold to select and fire, release to go back (impulse 69)")
        lines.extend(aliases)
        lines.append("")
    lines.extend(binds)
    lines.append("")
    return "\r\n".join(lines)


def key_conflicts(mod_key, mod_binds, general_binds):
    """Keys used by both a mod bind and a general bind: [(KEY, mod_label, general_label)].

    Not an error: the mod's binds.cfg runs last in that gamedir, so the mod bind wins
    there and the general bind still applies everywhere else."""
    from . import cfg
    general = {}
    for action_id, key in cfg.clean_binds(general_binds).items():
        general.setdefault(key.lower(), cfg.ACTION_BY_ID[action_id][2])
    labels = action_by_id(mod_key)
    out = []
    for action_id, key in sorted(clean_mod_binds(mod_key, mod_binds).items()):
        if key.lower() in general:
            out.append((key, labels[action_id][2], general[key.lower()]))
    return out


EXEC_LINE = "exec binds.cfg"
BASED_LINE = "exec based.cfg"
_TOP = "// Based Quake Installer: your name/binds/look (id1/based.cfg)"
_BOTTOM = "// Based Quake Installer: optional mod key binds"


def _find_ci(folder, name):
    """All entries in folder whose name matches ``name`` case-insensitively."""
    import os
    try:
        return [n for n in os.listdir(folder) if n.lower() == name.lower()]
    except OSError:
        return []


def merge_mod_autoexec(gamedir_path):
    """Make {gamedir}/autoexec.cfg run our shared cfg first and mod binds last.

    The mod's own autoexec contents (any filename case, e.g. AirQuake's AUTOEXEC.CFG)
    are preserved in the middle, so a mod's own binds override the shared ones and
    the optional Mod binds tab overrides both. Ends with a single lowercase
    autoexec.cfg. Idempotent. Returns the path written.
    """
    import os
    os.makedirs(gamedir_path, exist_ok=True)
    names = _find_ci(gamedir_path, "autoexec.cfg")
    body_parts = []
    # Lowercase (already merged) first, then any other-case copies the mod shipped.
    for n in sorted(names, key=lambda x: (x != "autoexec.cfg", x)):
        with open(os.path.join(gamedir_path, n), "r", encoding="utf-8",
                  errors="replace") as fh:
            body_parts.append(fh.read().replace("\r\n", "\n"))
    kept = []
    for part in body_parts:
        for line in part.split("\n"):
            st = line.strip().lower()
            if st in (EXEC_LINE, BASED_LINE) or line.strip() in (_TOP, _BOTTOM) or \
                    st == "// based quake installer: load optional mod key binds":
                continue
            kept.append(line)
    # de-duplicate when an old merged copy and the mod's original both exist
    if len(body_parts) > 1:
        seen, uniq = set(), []
        for line in kept:
            k = line.strip()
            if k and k in seen:
                continue
            seen.add(k)
            uniq.append(line)
        kept = uniq
    middle = "\n".join(kept).strip("\n")
    text = _TOP + "\n" + BASED_LINE + "\n\n"
    if middle:
        text += middle + "\n\n"
    text += _BOTTOM + "\n" + EXEC_LINE + "\n"
    for n in names:
        if n != "autoexec.cfg":
            os.remove(os.path.join(gamedir_path, n))
    path = os.path.join(gamedir_path, "autoexec.cfg")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", "\r\n"))
    binds = os.path.join(gamedir_path, "binds.cfg")
    if not _find_ci(gamedir_path, "binds.cfg"):
        with open(binds, "w", encoding="utf-8", newline="") as fh:
            fh.write("// binds.cfg -- optional Mod binds (none chosen)\r\n")
    return path


# --- Server-driven gamedir switch (e.g. joining a Thunderwalker server from base) ---
# FTE only re-runs its startup configs on a gamedir change when quake.rc, hexen.rc,
# default.cfg or server.cfg now resolve from a different place (fteqw fs.c
# FS_ChangeGame / conffile[]). Mods shipping none of those (Thunderwalker, Arena,
# ...) never ran autoexec.cfg -> binds.cfg after a server switch, so we give them a
# minimal quake.rc. Leaving the mod moves quake.rc back to id1's, so FTE reloads
# the base configs (unbindall) and mod binds don't stick.
# unezQuake never runs autoexec.cfg on a switch; it execs {gamedir}/frontend.cfg
# (cl_parse.c, cfg_legacy_exec), so each mod (and qw/ for going back) gets one.
FTE_RELOAD_TRIGGERS = ("quake.rc", "hexen.rc", "default.cfg", "server.cfg")
HOOK_MARK = "-- written by Based Quake Installer"
FTE_QUAKE_RC = (
    "// quake.rc " + HOOK_MARK + "\n"
    "// Lets FTE run autoexec.cfg (and binds.cfg) when a server switches to this mod.\n"
    "exec default.cfg\n"
    "exec config.cfg\n"
    "exec autoexec.cfg\n"
    "stuffcmds\n")
UNEZ_FRONTEND_CFG = (
    "// frontend.cfg " + HOOK_MARK + "\n"
    "// unezQuake runs this when a server switches to this game folder.\n"
    "exec autoexec.cfg\n")


def _archive_names(path):
    """Lowercase file names inside a .pak or .pk3 (empty on any error)."""
    import struct
    import zipfile
    try:
        if path.lower().endswith(".pak"):
            with open(path, "rb") as fh:
                magic, off, size = struct.unpack("<4sii", fh.read(12))
                if magic != b"PACK" or off < 12 or size < 0 or size % 64:
                    return set()
                fh.seek(off)
                data = fh.read(size)
            return {data[i:i + 56].split(b"\0", 1)[0].decode("latin-1").lower()
                    for i in range(0, len(data), 64)}
        with zipfile.ZipFile(path) as z:
            return {n.lower() for n in z.namelist()}
    except (OSError, ValueError, struct.error, zipfile.BadZipFile):
        return set()


def _is_ours(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return HOOK_MARK in fh.readline()
    except OSError:
        return False


def mod_has_fte_reload_trigger(gamedir_path):
    """True if the mod itself ships quake.rc/hexen.rc/default.cfg/server.cfg
    (loose or in a .pak/.pk3, any case). Our own quake.rc doesn't count."""
    import os
    try:
        names = os.listdir(gamedir_path)
    except OSError:
        return False
    for n in names:
        full = os.path.join(gamedir_path, n)
        if n.lower() in FTE_RELOAD_TRIGGERS and os.path.isfile(full) and not _is_ours(full):
            return True
        if n.lower().endswith((".pak", ".pk3")) and os.path.isfile(full):
            if _archive_names(full) & set(FTE_RELOAD_TRIGGERS):
                return True
    return False


def _write_hook(gamedir_path, name, text):
    import os
    path = os.path.join(gamedir_path, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", "\r\n"))
    return path


def ensure_switch_hook(gamedir_path, client):
    """Make a server-driven switch into this gamedir run autoexec.cfg -> binds.cfg.

    client is "FTE" or "unezQuake" (the client_dirs label). FTE: write quake.rc
    only when the mod has no reload trigger of its own (and drop a stale one of
    ours if the mod now ships one). unezQuake: write frontend.cfg, or add the exec
    line to a mod-shipped one. Idempotent. Returns the path written, or None.
    """
    import os
    if not os.path.isdir(gamedir_path):
        return None
    if client == "FTE":
        ours = [n for n in _find_ci(gamedir_path, "quake.rc")
                if _is_ours(os.path.join(gamedir_path, n))]
        if mod_has_fte_reload_trigger(gamedir_path):
            for n in ours:
                os.remove(os.path.join(gamedir_path, n))
            return None
        if _find_ci(gamedir_path, "quake.rc") and not ours:
            return None  # mod's own quake.rc (never overwrite)
        return _write_hook(gamedir_path, "quake.rc", FTE_QUAKE_RC)
    if client == "unezQuake":
        names = _find_ci(gamedir_path, "frontend.cfg")
        theirs = [n for n in names if not _is_ours(os.path.join(gamedir_path, n))]
        if not theirs:
            return _write_hook(gamedir_path, "frontend.cfg", UNEZ_FRONTEND_CFG)
        path = os.path.join(gamedir_path, theirs[0])
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            old = fh.read()
        if not any(l.strip().lower() == "exec autoexec.cfg" for l in old.splitlines()):
            with open(path, "a", encoding="utf-8", newline="") as fh:
                fh.write(("" if old.endswith("\n") or not old else "\r\n") +
                         "// Based Quake Installer: run autoexec.cfg on server switch\r\n"
                         "exec autoexec.cfg\r\n")
        return path
    return None


def ensure_autoexec_execs_binds(autoexec_path, text_if_new=None):
    """Back-compat wrapper: merge the gamedir autoexec. True if exec line was added."""
    import os
    before = ""
    if os.path.isfile(autoexec_path):
        with open(autoexec_path, "r", encoding="utf-8", errors="replace") as fh:
            before = fh.read()
    merge_mod_autoexec(os.path.dirname(autoexec_path) or ".")
    return EXEC_LINE not in before.replace("\r\n", "\n")
