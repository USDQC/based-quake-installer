"""Map tkinter key / mouse events to Quake key names (unezQuake and FTE).

Pure functions so they can be tested without a display. Every name returned is in
both engines' key tables (ezQuake keys.c / FTE keys.c) and passes cfg.normalize_key.
Quake binds physical keys, so shifted symbols map back to their US-layout key
(colon -> SEMICOLON, plus -> =, A -> a).
"""

# tkinter keysym -> Quake key name
_KEYSYMS = {
    "space": "SPACE", "Tab": "TAB", "ISO_Left_Tab": "TAB",
    "Return": "ENTER", "KP_Enter": "KP_ENTER", "BackSpace": "BACKSPACE",
    "Shift_L": "SHIFT", "Shift_R": "SHIFT",
    "Control_L": "CTRL", "Control_R": "CTRL",
    "Alt_L": "ALT", "Alt_R": "ALT", "Meta_L": "ALT", "Meta_R": "ALT",
    "ISO_Level3_Shift": "ALT",
    "Up": "UPARROW", "Down": "DOWNARROW", "Left": "LEFTARROW", "Right": "RIGHTARROW",
    "Insert": "INS", "Delete": "DEL", "Home": "HOME", "End": "END",
    "Prior": "PGUP", "Page_Up": "PGUP", "Next": "PGDN", "Page_Down": "PGDN",
    "Pause": "PAUSE", "Break": "PAUSE", "Caps_Lock": "CAPSLOCK",
    # keypad, Num Lock off
    "KP_Insert": "KP_INS", "KP_End": "KP_END", "KP_Down": "KP_DOWNARROW",
    "KP_Next": "KP_PGDN", "KP_Page_Down": "KP_PGDN", "KP_Left": "KP_LEFTARROW",
    "KP_Begin": "KP_5", "KP_Right": "KP_RIGHTARROW", "KP_Home": "KP_HOME",
    "KP_Up": "KP_UPARROW", "KP_Prior": "KP_PGUP", "KP_Page_Up": "KP_PGUP",
    "KP_Delete": "KP_DEL",
    # keypad, Num Lock on (same physical keys)
    "KP_0": "KP_INS", "KP_1": "KP_END", "KP_2": "KP_DOWNARROW", "KP_3": "KP_PGDN",
    "KP_4": "KP_LEFTARROW", "KP_5": "KP_5", "KP_6": "KP_RIGHTARROW",
    "KP_7": "KP_HOME", "KP_8": "KP_UPARROW", "KP_9": "KP_PGUP",
    "KP_Decimal": "KP_DEL", "KP_Separator": "KP_DEL",
    "KP_Divide": "KP_SLASH", "KP_Multiply": "KP_STAR",
    "KP_Subtract": "KP_MINUS", "KP_Add": "KP_PLUS",
    # punctuation (a raw ; would end the bind command, so it is SEMICOLON)
    "semicolon": "SEMICOLON", "colon": "SEMICOLON",
    "comma": ",", "less": ",", "period": ".", "greater": ".",
    "slash": "/", "question": "/", "backslash": "\\", "bar": "\\",
    "bracketleft": "[", "braceleft": "[", "bracketright": "]", "braceright": "]",
    "apostrophe": "'", "quoteright": "'", "quotedbl": "'",
    "grave": "`", "quoteleft": "`", "asciitilde": "`",
    "minus": "-", "underscore": "-", "equal": "=", "plus": "=",
    # shifted digits (US layout)
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4", "percent": "5",
    "asciicircum": "6", "ampersand": "7", "asterisk": "8",
    "parenleft": "9", "parenright": "0",
}
for _i in range(1, 13):
    _KEYSYMS["F%d" % _i] = "F%d" % _i

# Windows virtual-key codes, used only when the keysym is unknown (e.g. a non-US layout).
_WIN_VK = {186: "SEMICOLON", 187: "=", 188: ",", 189: "-", 190: ".", 191: "/",
           192: "`", 219: "[", 220: "\\", 221: "]", 222: "'"}

CANCEL = "Escape"


def key_from_keysym(keysym, keycode=None, windowing="x11"):
    """Quake key name for a tkinter KeyPress, or None if it can't be bound.

    Escape is not mapped (it cancels capture)."""
    ks = keysym or ""
    if ks in _KEYSYMS:
        return _KEYSYMS[ks]
    if len(ks) == 1 and ks.isascii() and (ks.isalpha() or ks.isdigit()):
        return ks.lower()
    if windowing == "win32" and keycode is not None:
        if 65 <= keycode <= 90 or 48 <= keycode <= 57:
            return chr(keycode).lower()
        if keycode in _WIN_VK:
            return _WIN_VK[keycode]
    return None


def key_from_button(num, windowing="x11"):
    """Quake key name for a tkinter mouse button number, or None.

    X11/Windows: 1 left, 2 middle, 3 right. macOS (aqua): 2 right, 3 middle.
    X11 reports the wheel as buttons 4/5 and side buttons as 8/9; Tk on Windows
    reports side buttons as 4/5 (8.6) or 8/9 (8.7)."""
    if windowing == "aqua":
        table = {1: "MOUSE1", 2: "MOUSE2", 3: "MOUSE3", 4: "MOUSE4", 5: "MOUSE5"}
    elif windowing == "win32":
        table = {1: "MOUSE1", 3: "MOUSE2", 2: "MOUSE3", 4: "MOUSE4", 5: "MOUSE5",
                 8: "MOUSE4", 9: "MOUSE5"}
    else:
        table = {1: "MOUSE1", 3: "MOUSE2", 2: "MOUSE3", 4: "MWHEELUP", 5: "MWHEELDOWN",
                 8: "MOUSE4", 9: "MOUSE5"}
    return table.get(num)


def key_from_wheel(delta):
    """<MouseWheel> delta (Windows/macOS) -> MWHEELUP / MWHEELDOWN."""
    if not delta:
        return None
    return "MWHEELUP" if delta > 0 else "MWHEELDOWN"


def all_names():
    """Every name these maps can produce (for tests)."""
    names = set(_KEYSYMS.values()) | set(_WIN_VK.values())
    names |= {"MOUSE%d" % i for i in range(1, 6)} | {"MWHEELUP", "MWHEELDOWN"}
    names |= set("abcdefghijklmnopqrstuvwxyz0123456789")
    return sorted(names)

