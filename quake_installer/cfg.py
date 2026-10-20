"""autoexec.cfg generation.

Each client tree gets its OWN autoexec.cfg text (FTE look block vs UnezQuake look
block); nothing is shared between the two trees.

Binds come from a dict of action_id -> Quake key name. Blank / missing actions are
skipped (left unbound). Optional presets (Default/vanilla fills from stock default.cfg; Clear empties)
only populate that dict; they are not baked into the cfg writer. GUI exposes
Default + Clear only; WASD/Modern remain for CLI/legacy.
"""

import re

from .constants import LOOK_GL, MAX_NAME_LEN
from . import sb_sources

CLIENT_FTE = "fte"
CLIENT_UNEZ = "unez"

# --- editable bind actions (id, quake command, UI label) ---------------------------

# Classic QuakeWorld Customize Controls (movement/look/swim + attack/change weapon),
# then a weapons section (impulse 0–8). Labels match the stock QW menu wording.
BIND_ACTIONS = [
    # --- QW Customize Controls ---
    ("attack", "+attack", "Attack"),
    ("changeweapon", "impulse 10", "Change weapon"),
    ("jump", "+jump", "Jump / swim up"),
    ("forward", "+forward", "Walk forward"),
    ("back", "+back", "Backpedal"),
    ("left", "+left", "Turn left"),
    ("right", "+right", "Turn right"),
    ("speed", "+speed", "Run"),
    ("moveleft", "+moveleft", "Step left"),
    ("moveright", "+moveright", "Step right"),
    ("strafe", "+strafe", "Sidestep"),
    ("lookup", "+lookup", "Look up"),
    ("lookdown", "+lookdown", "Look down"),
    ("centerview", "centerview", "Center view"),
    ("mouse_mlook", "+mlook", "Mouse look"),
    ("klook", "+klook", "Keyboard look"),
    ("moveup", "+moveup", "Swim up"),
    ("movedown", "+movedown", "Swim down"),
    ("showscores", "+showscores", "Show scoreboard"),
    # --- Weapons (stock impulse slots) ---
    ("impulse1", "impulse 1", "Weapon 1 (axe)"),
    ("impulse2", "impulse 2", "Weapon 2 (shotgun)"),
    ("impulse3", "impulse 3", "Weapon 3 (ssg)"),
    ("impulse4", "impulse 4", "Weapon 4 (nailgun)"),
    ("impulse5", "impulse 5", "Weapon 5 (sng)"),
    ("impulse6", "impulse 6", "Weapon 6 (grenade)"),
    ("impulse7", "impulse 7", "Weapon 7 (rocket)"),
    ("impulse8", "impulse 8", "Weapon 8 (shaft)"),
    ("impulse0", "impulse 0", "Weapon 0"),
]

ACTION_BY_ID = {a[0]: a for a in BIND_ACTIONS}

# Stock misc binds always appended unless the key was already used by the player.
STOCK_MISC = [
    ("PAUSE", "pause"),
    ("ESCAPE", "togglemenu"),
    ("~", "toggleconsole"),
    ("`", "toggleconsole"),
    ("+", "sizeup"),
    ("=", "sizeup"),
    ("-", "sizedown"),
    ("F12", "screenshot"),
    ("\\", "+mlook"),
]

# Known / accepted Quake key tokens (case-insensitive match; output form on the right).
_SPECIAL_KEYS = {
    "SPACE": "SPACE", "CTRL": "CTRL", "CONTROL": "CTRL", "ALT": "ALT",
    "SHIFT": "SHIFT", "TAB": "TAB", "ENTER": "ENTER", "RETURN": "ENTER",
    "ESCAPE": "ESCAPE", "ESC": "ESCAPE", "SEMICOLON": "SEMICOLON",
    "UPARROW": "UPARROW", "DOWNARROW": "DOWNARROW",
    "LEFTARROW": "LEFTARROW", "RIGHTARROW": "RIGHTARROW",
    "HOME": "HOME", "END": "END", "PGUP": "PGUP", "PGDN": "PGDN",
    "INS": "INS", "INSERT": "INS", "DEL": "DEL", "DELETE": "DEL",
    "PAUSE": "PAUSE", "BACKSPACE": "BACKSPACE",
    "MOUSE1": "MOUSE1", "MOUSE2": "MOUSE2", "MOUSE3": "MOUSE3",
    "MOUSE4": "MOUSE4", "MOUSE5": "MOUSE5",
    "MWHEELUP": "MWHEELUP", "MWHEELDOWN": "MWHEELDOWN",
    "KP_INS": "KP_INS", "KP_END": "KP_END", "KP_DOWNARROW": "KP_DOWNARROW",
    "KP_PGDN": "KP_PGDN", "KP_LEFTARROW": "KP_LEFTARROW", "KP_5": "KP_5",
    "KP_RIGHTARROW": "KP_RIGHTARROW", "KP_HOME": "KP_HOME",
    "KP_UPARROW": "KP_UPARROW", "KP_PGUP": "KP_PGUP", "KP_DEL": "KP_DEL",
    "KP_SLASH": "KP_SLASH", "KP_MINUS": "KP_MINUS", "KP_PLUS": "KP_PLUS",
    "KP_ENTER": "KP_ENTER", "KP_MULTIPLY": "KP_MULTIPLY", "KP_STAR": "KP_STAR",
    "CAPSLOCK": "CAPSLOCK",
}
for _i in range(1, 13):
    _SPECIAL_KEYS["F%d" % _i] = "F%d" % _i

# Single-character punctuation that Quake accepts as key names.
_PUNCT_KEYS = set("\\,./[];'`~-=+")

_KEY_RE = re.compile(r"^[A-Za-z0-9_\\,./\[\];'`~\-=+]+$")


def normalize_key(raw):
    """Validate and normalize a Quake key name. Empty -> ''; invalid -> ValueError."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if any(c in s for c in '"\n\r\t;'):
        raise ValueError("key must not contain quotes, semicolons, or whitespace: %r" % raw)
    if " " in s:
        raise ValueError("key must be a single Quake key name (no spaces): %r" % raw)
    if not _KEY_RE.match(s):
        raise ValueError("unsupported key characters: %r" % raw)
    upper = s.upper()
    if upper in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[upper]
    if len(s) == 1:
        if s.isalpha():
            return s.lower()
        if s.isdigit() or s in _PUNCT_KEYS:
            return s
        raise ValueError("unsupported key: %r" % raw)
    # Multi-char unknown: accept uppercase form if it looks like a Quake token.
    if s.isalnum() or "_" in s:
        return upper
    raise ValueError("unsupported key: %r" % raw)


def clean_binds(binds):
    """Return {action_id: normalized_key} omitting blanks; raise ValueError on bad keys."""
    out = {}
    for action_id, raw in (binds or {}).items():
        if action_id not in ACTION_BY_ID:
            continue
        key = normalize_key(raw)
        if key:
            out[action_id] = key
    return out


# --- presets (fill the bind editor; not written directly) -------------------------

# From stock Quake 1.06 / QuakeWorld default.cfg (pak0) Customize Controls + weapons.
PRESET_VANILLA = {
    "attack": "CTRL",
    "changeweapon": "/",
    "jump": "SPACE",
    "forward": "UPARROW",
    "back": "DOWNARROW",
    "left": "LEFTARROW",
    "right": "RIGHTARROW",
    "speed": "SHIFT",
    "moveleft": ",",
    "moveright": ".",
    "strafe": "ALT",
    "lookup": "a",
    "lookdown": "z",
    "centerview": "END",
    "mouse_mlook": "\\",
    "klook": "INS",
    "moveup": "d",
    "movedown": "c",
    "showscores": "TAB",
    "impulse1": "1",
    "impulse2": "2",
    "impulse3": "3",
    "impulse4": "4",
    "impulse5": "5",
    "impulse6": "6",
    "impulse7": "7",
    "impulse8": "8",
    "impulse0": "0",
}

# Legacy CLI-only overlay (GUI exposes Default + Clear only).
PRESET_WASD = {
    "forward": "w",
    "back": "s",
    "moveleft": "a",
    "moveright": "d",
    "left": "LEFTARROW",
    "right": "RIGHTARROW",
    "jump": "SPACE",
    "speed": "SHIFT",
    "attack": "MOUSE1",
    "movedown": "CTRL",
    "strafe": "ALT",
    "lookup": "PGDN",
    "lookdown": "DEL",
    "centerview": "END",
    "mouse_mlook": "MOUSE3",
    "klook": "INS",
}

PRESET_MODERN = {
    "impulse1": "1",
    "impulse2": "q",
    "impulse3": "e",
    "impulse4": "c",
    "impulse5": "v",
    "impulse6": "x",
    "impulse7": "r",
    "impulse8": "f",
}

PRESETS = {
    "vanilla": PRESET_VANILLA,
    "wasd": PRESET_WASD,
    "modern": PRESET_MODERN,
}


def binds_from_legacy(movement="vanilla", weapons="vanilla"):
    """Build a binds dict from the old movement/weapons CLI choices."""
    binds = dict(PRESET_VANILLA)
    if movement == "wasd":
        binds.update(PRESET_WASD)
    if weapons == "modern":
        binds.update(PRESET_MODERN)
    return binds


BASE_SETTINGS = """viewsize 100
gamma 1.0
volume 0.7
sensitivity 3
m_pitch 0.022
+mlook"""

# Cvar names differ per engine. A real unezQuake 2.1 run reported "Unknown command" for
# mlook_enabled / r_particles / r_particle_type / anisotropicfilter_extent; the ezQuake
# names are freelook / r_drawparticles / gl_anisotropy.
SPRAY_IMAGE = "usdqc"  # qw/sprays/usdqc.png from the spray pack

CLIENT_BASE = {
    "fte": "mlook_enabled 1",
    # sb/sources.txt is written by sb_sources.write_sources(); ezQuake only auto-ticks
    # "id limbo"/"Global"/"QuakeServers.net"/"Asgaard", so tick every source we ship.
    # Sources load before configs run, so these work from based.cfg.
    # crosshair: unezQuake's default is 4; 1 is the classic "+".
    "unez": "freelook 1\ncrosshair 1\n\n// === server browser: tick the installer's sources (sb/sources.txt) ===\n"
            + "\n".join(sb_sources.sourcemark_lines())
            # Sprays (unezQuake 2.1.1 cl_sprays.c): images load from qw/sprays
            # (cl_spray_image_path); cl_spray_image defaults to "spray", which the spray
            # pack doesn't ship, so point it at the pack's image. Use with +spray.
            + "\n\n// === sprays: qw/sprays (bind a key to +spray) ===\ncl_spray_image " + SPRAY_IMAGE,
}

LOOK_BLOCKS = {
    (CLIENT_FTE, "soft"): """r_softwarebanding 1
gl_affinemodels 1
gl_texturemode GL_NEAREST_MIPMAP_NEAREST
gl_texturemode2d GL_NEAREST
r_particlesystem classic
r_part_classic_square 1
r_part_classic_opaque 1
r_dynamic 1
vid_conautoscale 0""",
    (CLIENT_FTE, "gl"): """r_softwarebanding 0
gl_affinemodels 0
gl_texturemode GL_LINEAR_MIPMAP_LINEAR
gl_texturemode2d GL_LINEAR
r_particlesystem script
r_part_classic_square 0
r_part_classic_opaque 0
r_dynamic 1
vid_renderer gl""",
    # Square, unfiltered pixels (names/defaults checked in unezQuake 2.1.1 source):
    # world + gun nearest-filtered, no lerp on resampled images, no smoothing of
    # text/crosshair/HUD pics, framebuffer upscale unsmoothed, and the 2D layer
    # auto-sized at a uniform integer scale (no stretch, correct aspect).
    # Particles: solid square classic particles (gl_squareparticles 1; the texture is
    # mipmapped so gl_texturemode keeps it unfiltered); blood trails and bubbles use
    # classic particles instead of the round QMB ones (their defaults are 1).
    (CLIENT_UNEZ, "soft"): """gl_texturemode GL_NEAREST_MIPMAP_NEAREST
gl_texturemode_viewmodels GL_NEAREST
gl_lerpimages 0
gl_anisotropy 1
r_smoothtext 0
r_smoothcrosshair 0
r_smoothimages 0
vid_framebuffer_smooth 0
vid_conwidth 0
vid_conheight 0
vid_conscale 2
r_drawparticles 1
gl_squareparticles 1
gl_part_bloodtrails 0
gl_part_bubble 0
gl_flashblend 0
r_dynamic 1
r_bloom 0""",
    (CLIENT_UNEZ, "gl"): """gl_texturemode GL_LINEAR_MIPMAP_LINEAR
r_drawparticles 1
gl_flashblend 1
r_dynamic 1
gl_anisotropy 8""",
}

CLIENT_LABEL = {CLIENT_FTE: "FTE", CLIENT_UNEZ: "UnezQuake"}


def sanitize_name(name):
    """Make a player name safe inside a quoted Quake console string.

    Quake's tokenizer has no escape for a double quote inside a quoted string,
    so '"' becomes "'" and control characters/newlines are removed.
    """
    name = (name or "").replace('"', "'")
    name = "".join(ch for ch in name if ch >= " " and ch != "\x7f")
    name = name.strip()
    if not name:
        name = "player"
    return name[:MAX_NAME_LEN]


def _fmt_bind(key, cmd):
    if " " in cmd or ";" in cmd:
        return 'bind %s "%s"' % (key, cmd)
    return "bind %s %s" % (key, cmd)


def build_binds(binds):
    """Return ordered [(section_title, [(key, cmd), ...])].

    Player binds first (blank actions skipped). Each key appears once: if two
    actions share a key, the later BIND_ACTIONS entry wins. Stock misc binds are
    appended only for keys the player did not already use.
    """
    cleaned = clean_binds(binds)
    seen = set()
    player = []
    for action_id, cmd, _label in BIND_ACTIONS:
        if action_id not in cleaned:
            continue
        key = cleaned[action_id]
        kl = key.lower()
        if kl in seen:
            player = [(k, c) for k, c in player if k.lower() != kl]
        seen.add(kl)
        player.append((key, cmd))

    misc = []
    for key, cmd in STOCK_MISC:
        kl = key.lower()
        if kl in seen:
            continue
        seen.add(kl)
        misc.append((key, cmd))

    sections = []
    if player:
        sections.append(("player binds", player))
    if misc:
        sections.append(("misc (stock)", misc))
    return sections


def render_autoexec(client, player_name, binds, look):
    """Render the autoexec.cfg text for one client (CLIENT_FTE or CLIENT_UNEZ).

    binds: dict action_id -> key (blank/missing skipped). Also accepts the legacy
    (movement, weapons) call shape via binds_from_legacy if binds is a str — no,
    callers must pass a dict. Use binds_from_legacy() for CLI presets.
    """
    if client not in (CLIENT_FTE, CLIENT_UNEZ):
        raise ValueError("unknown client %r" % client)
    look_key = "gl" if look == LOOK_GL else "soft"
    name = sanitize_name(player_name)
    look_label = "OpenGL look" if look_key == "gl" else "Software-rendered look"

    bound = clean_binds(binds)
    n_bound = len(bound)

    lines = [
        "// autoexec.cfg for %s -- generated by Based Quake Installer" % CLIENT_LABEL[client],
        "// options: custom binds (%d actions), look=%s" % (n_bound, look_label),
        "// This file belongs to this client tree only (not shared with the other client).",
        "",
        "// === USDQC first-run: identity ===",
        'name "%s"' % name,
        "",
        "// === binds (blank fields were left unbound) ===",
        "unbindall",
    ]
    for title, pairs in build_binds(bound):
        lines.append("")
        lines.append("// " + title)
        for key, cmd in pairs:
            lines.append(_fmt_bind(key, cmd))
    lines.append("")
    lines.append(BASE_SETTINGS)
    lines.append(CLIENT_BASE.get(client, ""))
    lines.append("")
    lines.append("// === %s: %s ===" % (CLIENT_LABEL[client], look_label))
    lines.append(LOOK_BLOCKS[(client, look_key)])
    lines.append("")
    return "\r\n".join("\n".join(lines).split("\n"))
