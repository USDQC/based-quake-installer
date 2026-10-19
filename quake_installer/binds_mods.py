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


def ensure_autoexec_execs_binds(autoexec_path, text_if_new=None):
    """Back-compat wrapper: merge the gamedir autoexec. True if exec line was added."""
    import os
    before = ""
    if os.path.isfile(autoexec_path):
        with open(autoexec_path, "r", encoding="utf-8", errors="replace") as fh:
            before = fh.read()
    merge_mod_autoexec(os.path.dirname(autoexec_path) or ".")
    return EXEC_LINE not in before.replace("\r\n", "\n")
