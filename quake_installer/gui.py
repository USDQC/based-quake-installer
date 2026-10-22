"""tkinter GUI (stdlib only). Install work runs in a background thread; the UI
is updated through a queue polled with Tk.after (Tk is not thread-safe).

This app is an installer only: progress + options. It installs engines and all
configured mods together. It does not launch games, write .bat helpers, or
create desktop shortcuts. FTE gets DISABLEHOMEDIR via default.fmf (full install).
"Mods only (existing clients)" installs just mods/configs into the user's own
unezQuake/FTE folders and leaves the clients and FTE's home-dir mode alone.
"""

import os
import queue
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, cfg, binds_mods, keycapture, mods as modlib, selfupdate, settings
from .constants import (APP_TITLE, DEFAULT_ROOT, FTE_DIRNAME, LOOK_GL, LOOK_SOFT,
                        MAX_NAME_LEN, PLATFORM_LABELS, UNEZ_DIRNAME, host_platform)
from .installer import Cancelled, InstallError, Options, Reporter, run_install
from .paths import IS_WINDOWS
from . import existing as existing_mod, folders

MODE_FULL = "full"
MODE_EXISTING = "existing"
MODE_LABELS = ((MODE_FULL, "Full install"), (MODE_EXISTING, "Mods only (existing clients)"))

THEMES = (("classic", "Classic"), ("sv-dark", "Dark"))
# Colours for the plain tk widgets (Text, Canvas, KeyBox entries) and muted labels.
PALETTES = {
    "light": {"bg": None, "field": "white", "fg": "black", "disabled": "#eeeeee",
              "capture": "#ffe680", "capture_fg": "black", "accent": "#1a6fd1",
              "border": "#9a9a9a", "hover": "#5b8fd6", "dim": None, "muted": "#555", "link": "#1a4f8b",
              "err": "#b00020", "ok": "#1b5e20", "warn": "#8a6d00", "text_bg": "white"},
    "dark": {"bg": "#1c1c1c", "field": "#2b2b2b", "fg": "#e6e6e6", "disabled": "#3a3a3a",
             "capture": "#0f4c81", "capture_fg": "#ffffff", "accent": "#57c8ff",
             "border": "#4a4a4a", "hover": "#8fb8e8", "dim": "#8c8c8c", "muted": "#a8a8a8", "link": "#8ab4f8",
             "err": "#ff8a80", "ok": "#81c784", "warn": "#ffd54f", "text_bg": "#232323"},
}


def _load_sv_ttk():
    """sv_ttk if installed, else the vendored copy; None if neither works."""
    try:
        import sv_ttk
        return sv_ttk
    except ImportError:
        pass
    try:
        from .vendor import sv_ttk
        return sv_ttk
    except ImportError:
        return None


def center_window(win, parent=None, margin_x=0, margin_y=0):
    """Place win centered on parent (if given & mapped) or on its screen, without
    a visible jump. Sizes are in real pixels, so this works with DPI scaling.

    margin_x/margin_y keep the window clear of the screen edges (title bar, taskbar).
    """
    win.update_idletasks()
    w = max(win.winfo_width(), win.winfo_reqwidth())
    h = max(win.winfo_height(), win.winfo_reqheight())
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(w, max(320, sw - 2 * margin_x))
    h = min(h, max(240, sh - 2 * margin_y))
    if parent is not None and parent.winfo_ismapped():
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    else:
        x, y = (sw - w) // 2, (sh - h) // 2
    x = max(margin_x, min(x, sw - w - margin_x))
    y = max(margin_y, min(y, sh - h - margin_y))
    win.geometry("%dx%d+%d+%d" % (w, h, x, y))
    return x, y, w, h


def paths_hint(existing, root, install_unez=True, install_fte=True,
               unez_target="", fte_target="", unez_path="", fte_path="",
               exists=os.path.isdir):
    """Folder hint under the install-mode row; pure so it is unit tested."""
    def clean(p):
        p = str(p or "").strip().strip('"')
        return os.path.normpath(os.path.expanduser(p)) if p else ""

    def mark(path):
        return "%s (%s)" % (path, "existing" if exists(path) else "new")

    if existing:
        paths = [p for p in (clean(unez_path), clean(fte_path)) if p]
        if not paths:
            return "Choose the unezQuake and/or FTE folder you already have."
        return "Mods go into: " + " and ".join(mark(p) for p in paths)
    root_dir = clean(root) or DEFAULT_ROOT
    paths = []
    if install_unez:
        paths.append(mark(clean(unez_target) or os.path.join(root_dir, UNEZ_DIRNAME)))
    if install_fte:
        paths.append(mark(clean(fte_target) or os.path.join(root_dir, FTE_DIRNAME)))
    if not paths:
        return "No engine is turned on. Open Settings to choose one."
    return "Installs to: " + " and ".join(paths)


def _enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _fmt_bytes(n):
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%.1f %s" % (n, unit)) if unit != "B" else ("%d B" % n)
        n /= 1024.0


class QueueReporter(Reporter):
    def __init__(self, q):
        self.q = q

    def log(self, msg):
        self.q.put(("log", msg))

    def step(self, index, total, title):
        self.q.put(("step", (index, total, title)))

    def progress(self, done, total):
        self.q.put(("progress", (done, total)))


# Short display names for the included-mods panel (UI only).
_MOD_SHORT_TITLES = {
    "airquake": "AirQuake",
    "painkeep": "PainKeep",
    "hh": "Headhunters",
    "fortress": "Team Fortress",
    "thunderwalker": "Thunderwalker CTF",
    "arena": "Rocket Arena",
    "fvf": "Future vs Fantasy",
    "rally": "Quake Rally",
    "grq": "Get Rich Quake",
    "runequake": "Rune Quake",
}


def _clients_label(spec):
    """Return 'FTE' when the mod is FTE-only; else '' (dual-client mods need no tag)."""
    clients = spec.get("clients") or ["fte"]
    if list(clients) == ["fte"]:
        return "FTE"
    return ""


def _mod_list_line(spec):
    name = _MOD_SHORT_TITLES.get(spec.get("key"), spec.get("title", spec.get("key", "?")))
    tag = _clients_label(spec)
    return ("• %s (%s)" % (name, tag)) if tag else ("• %s" % name)


BIND_HELP = "Click a box, then press the key or mouse button you want. Click ✕ to clear a bind."
_PROMPT = "Press a key…"


class KeyBox(object):
    """A bind box that captures a key or mouse button instead of free typing.

    Click it -> 'Press a key…'; the next key, mouse button or wheel turn fills it
    with the Quake key name. Escape (or leaving the window) cancels and keeps the
    old value. The real value lives in ``var``; the box only displays it.
    """

    active = None  # the KeyBox currently capturing, if any
    pal = PALETTES["light"]
    instances = []

    def __init__(self, parent, var, width=14, on_change=None):
        self.var = var
        self.on_change = on_change
        self.capturing = False
        self.enabled = True
        self.shown = tk.StringVar(value=var.get())
        var.trace_add("write", lambda *a: self._sync())
        self.entry = tk.Entry(parent, textvariable=self.shown, width=width,
                              state="readonly", cursor="hand2", relief="solid", bd=1,
                              readonlybackground=KeyBox.pal["field"],
                              fg=KeyBox.pal["fg"],
                              disabledbackground=KeyBox.pal["disabled"], takefocus=0,
                              highlightthickness=2,
                              highlightbackground=KeyBox.pal["border"],
                              highlightcolor=KeyBox.pal["border"])
        self.hover = False
        KeyBox.instances.append(self)
        self._ws = self.entry.tk.call("tk", "windowingsystem")
        e = self.entry
        e.bind("<ButtonPress>", self._on_button)
        e.bind("<KeyPress>", self._on_key)
        e.bind("<MouseWheel>", self._on_wheel)
        e.bind("<FocusOut>", lambda _e: self.cancel())
        e.bind("<Enter>", lambda _e: self._set_hover(True))
        e.bind("<Leave>", lambda _e: self._set_hover(False))
        self.btn = ttk.Button(parent, text="✕", width=2, command=self.clear, takefocus=0,
                              style="Clear.TButton")

    def grid(self, row, column, **kw):
        self.entry.grid(row=row, column=column, sticky="w", pady=1)
        self.btn.grid(row=row, column=column + 1, sticky="w", padx=(1, kw.get("gap", 14)),
                      pady=1)

    def _sync(self):
        if not self.capturing:
            self.shown.set(self.var.get())

    def _set_hover(self, on):
        self.hover = on
        self.recolor()

    def recolor(self):
        """Capturing: accent border + distinct fill; hover: lighter border."""
        p = KeyBox.pal
        if self.capturing:
            ring, bg, fg = p["accent"], p["capture"], p["capture_fg"]
        else:
            ring = p["hover"] if self.hover and self.enabled else p["border"]
            bg, fg = p["field"], p["fg"]
        self.entry.configure(readonlybackground=bg, fg=fg, disabledbackground=p["disabled"],
                             disabledforeground="#888", highlightbackground=ring,
                             highlightcolor=ring)

    def set_enabled(self, enabled):
        if not enabled:
            self.cancel()
        self.enabled = enabled
        self.entry.configure(state="readonly" if enabled else "disabled")
        self.btn.configure(state="normal" if enabled else "disabled")

    def clear(self):
        self.cancel()
        self.var.set("")

    def start(self):
        if KeyBox.active is not None and KeyBox.active is not self:
            KeyBox.active.cancel()
        KeyBox.active = self
        self.capturing = True
        self.shown.set(_PROMPT)
        self.recolor()
        self.entry.focus_set()
        try:
            self.entry.grab_set()  # mouse buttons anywhere in the window go to this box
        except tk.TclError:
            pass

    def _finish(self):
        self.capturing = False
        if KeyBox.active is self:
            KeyBox.active = None
        try:
            self.entry.grab_release()
        except tk.TclError:
            pass
        self.recolor()
        self.shown.set(self.var.get())

    def cancel(self):
        if self.capturing:
            self._finish()

    def accept(self, key):
        self._finish()
        self.var.set(key)
        if self.on_change:
            self.on_change(self, key)

    def _on_button(self, event):
        if not self.enabled:
            return "break"
        if not self.capturing:
            if event.num == 1:
                self.start()
                return "break"
            return None  # let the wheel (X11 buttons 4/5) scroll the page
        # Clicking this box's own ✕ while it waits clears it instead of binding MOUSE1.
        if event.num == 1:
            try:
                hit = self.entry.winfo_containing(event.x_root, event.y_root)
            except (tk.TclError, KeyError):
                hit = None
            if hit is self.btn:
                self.clear()
                return "break"
        key = keycapture.key_from_button(event.num, self._ws)
        if key:
            self.accept(key)
        return "break"

    def _on_wheel(self, event):
        if self.capturing:
            key = keycapture.key_from_wheel(event.delta)
            if key:
                self.accept(key)
            return "break"
        return None

    def _on_key(self, event):
        if not self.capturing:
            return "break"
        if event.keysym == keycapture.CANCEL:
            self.cancel()
            return "break"
        key = keycapture.key_from_keysym(event.keysym, event.keycode, self._ws)
        if key:
            self.accept(key)
        return "break"


class _Tooltip(object):
    """Minimal hover label (ttk has no tooltip); used by the cog button."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry("+%d+%d" % (x, y))
        ttk.Label(self.tip, text=self.text, padding=(6, 2),
                  style="Muted.TLabel").pack()

    def _hide(self, _event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class InstallerApp(object):
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()
        self.result = None
        self.last_opts = None
        self._step = (0, 6)

        root.withdraw()  # placed centered once built (no visible jump)
        root.title("%s  v%s" % (APP_TITLE, __version__))
        root.minsize(960, 680)
        self.classic_theme = "vista" if IS_WINDOWS else "clam"
        try:
            ttk.Style().theme_use(self.classic_theme)
        except tk.TclError:
            pass
        self.classic_style = ttk.Style().configure(".")  # restored after Dark
        ttk.Style().configure("Clear.TButton", padding=(2, 0))
        self.var_theme = tk.StringVar(value=THEMES[0][1])
        self.canvases = []
        self.var_mode = tk.StringVar(value=MODE_FULL)
        self.var_unez = tk.StringVar()
        self.var_fte = tk.StringVar()
        self.var_fte_cfg = tk.StringVar()
        self.fte_cfg_choice = {}  # fte folder -> "home" / "install" (user answered)

        self.var_root = tk.StringVar(value=DEFAULT_ROOT)
        self.var_name = tk.StringVar(value="player")
        self.var_look = tk.StringVar(value=LOOK_SOFT)
        # Settings: which engines a full install creates, where, and whether the
        # folder fields are remembered between runs (all on by default).
        self.var_install_unez = tk.BooleanVar(value=True)
        self.var_install_fte = tk.BooleanVar(value=True)
        self.var_unez_target = tk.StringVar()
        self.var_fte_target = tk.StringVar()
        self.var_remember_dirs = tk.BooleanVar(value=True)
        self._gear_cache = {}
        self.settings_window = None
        self.update_window = None
        self.platform = host_platform()  # always the OS we run on
        self.var_status = tk.StringVar(value="Ready.")
        self.var_paths = tk.StringVar()
        self.var_self = tk.StringVar()  # quiet "new installer available" notice
        self.var_self_auto = tk.BooleanVar(value=True)
        self.self_worker = None
        self.mod_specs = modlib.load_specs()
        self.bind_vars = {}   # action_id -> StringVar (start empty)
        self.bind_entries = []
        self.bind_boxes = []  # KeyBox widgets (general + every mod page)
        self.mod_bind_vars = {}  # mod_key -> {action_id -> StringVar}
        self.radios = []
        self.preset_buttons = []

        self._build()
        self._load_settings()
        self.var_root.trace_add("write", lambda *a: self._update_paths())
        self.var_unez_target.trace_add("write", lambda *a: self._update_paths())
        self.var_fte_target.trace_add("write", lambda *a: self._update_paths())
        self.var_install_unez.trace_add("write", lambda *a: self._update_paths())
        self.var_install_fte.trace_add("write", lambda *a: self._update_paths())
        self.var_fte.trace_add("write", lambda *a: self._update_fte_cfg())
        self.var_unez.trace_add("write", lambda *a: self._update_fte_cfg())
        self.var_unez.trace_add("write", lambda *a: self._update_paths())
        self.var_fte.trace_add("write", lambda *a: self._update_paths())
        self._update_paths()
        self._show_mode()
        self._update_fte_cfg()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.minsize(min(960, max(760, sw - 80)), min(760, max(560, sh - 144)))
        center_window(root, margin_x=24, margin_y=72)
        root.deiconify()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Control-comma>", lambda _e: self._open_settings())
        root.after(100, self._poll)
        selfupdate.cleanup_old()  # the exe left over from the last self-update
        if self.var_self_auto.get():
            root.after(1500, lambda: self._start_self_check(quiet=True))

    def _main_wheel(self, event):
        """Wheel over the main window scrolls it, except over self-scrolling widgets."""
        try:
            if event.widget is None or event.widget.winfo_toplevel() is not self.root:
                return
        except tk.TclError:
            return
        if isinstance(event.widget, (tk.Text, tk.Listbox, ttk.Combobox)):
            return
        num = getattr(event, "num", None)
        if num == 4:
            self.main_canvas.yview_scroll(-2, "units")
        elif num == 5:
            self.main_canvas.yview_scroll(2, "units")
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            self.main_canvas.yview_scroll(
                int(-delta / (120 if IS_WINDOWS else 1)) or (-1 if delta > 0 else 1),
                "units")
        return "break"

    # ------------------------------------------------------------------ layout
    def _build(self):
        pad = {"padx": 6, "pady": 3}
        # The main window scrolls if DPI scaling makes it taller than the
        # screen; the scrollbar is always visible so the layout never clips.
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        self.main_canvas = tk.Canvas(shell, highlightthickness=0)
        self.canvases.append(self.main_canvas)  # _recolor keeps it on the theme colour
        self.main_scroll = ttk.Scrollbar(shell, orient="vertical",
                                         command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scroll.set)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.main_scroll.grid(row=0, column=1, sticky="ns")
        # holder fills the whole visible canvas; outer sits at its top and keeps its
        # natural height, so growing or shrinking content re-triggers _sync.
        holder = ttk.Frame(self.main_canvas)
        holder.pack_propagate(False)
        outer = ttk.Frame(holder, padding=10)
        outer.pack(side="top", fill="x", anchor="n")
        self.main_window = self.main_canvas.create_window((0, 0), window=holder,
                                                          anchor="nw")

        def _sync(_e=None):
            # Fill the visible area too, so no bare canvas shows below the content.
            self.main_canvas.itemconfigure(
                self.main_window, width=self.main_canvas.winfo_width(),
                height=max(outer.winfo_reqheight(), self.main_canvas.winfo_height()))
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        outer.bind("<Configure>", _sync)
        self.main_canvas.bind("<Configure>", _sync)
        self.root.bind("<MouseWheel>", self._main_wheel)
        self.root.bind("<Button-4>", self._main_wheel)
        self.root.bind("<Button-5>", self._main_wheel)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(2, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        head = ttk.Frame(outer)
        head.grid(row=0, column=0, columnspan=2, sticky="e")
        ttk.Label(
            head, style="Muted.TLabel",
            text="Installs unezQuake, FTE and classic QuakeWorld mods."
        ).pack(side="left")
        # Settings lives behind the cog (theme + update check moved inside).
        self.btn_settings = ttk.Button(head, image=self._gear_image(),
                                       command=self._open_settings)
        self.btn_settings.pack(side="left", padx=(12, 0))
        self._settings_tip = _Tooltip(self.btn_settings, "Settings (Ctrl+,)")

        # Install mode + folder(s)
        f = ttk.LabelFrame(outer, text="Install folder", padding=6)
        f.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        f.columnconfigure(0, weight=1)
        self.frm_install = f
        mrow = ttk.Frame(f)
        mrow.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(mrow, text="Install mode:").pack(side="left")
        self.mode_radios = []
        for val, text in MODE_LABELS:
            rb = ttk.Radiobutton(mrow, text=text, value=val, variable=self.var_mode,
                                 command=self._show_mode)
            rb.pack(side="left", padx=(8, 0))
            self.mode_radios.append(rb)
        # full install: one root folder
        self.frm_full = ttk.Frame(f)
        self.frm_full.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.frm_full.columnconfigure(0, weight=1)
        self.ent_root = ttk.Entry(self.frm_full, textvariable=self.var_root)
        self.ent_root.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_browse = ttk.Button(self.frm_full, text="Browse...", command=self._browse)
        self.btn_browse.grid(row=0, column=1)
        # mods only: the user's own client folders (leave one empty if you don't have it)
        self.frm_exist = ttk.Frame(f)
        self.frm_exist.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.frm_exist.columnconfigure(1, weight=1)
        self.exist_widgets = []
        for r, (label, var, kind) in enumerate((("unezQuake folder:", self.var_unez, "unez"),
                                                ("FTE folder:", self.var_fte, "fte"))):
            ttk.Label(self.frm_exist, text=label).grid(row=r, column=0, sticky="w")
            ent = ttk.Entry(self.frm_exist, textvariable=var)
            ent.grid(row=r, column=1, sticky="ew", padx=6, pady=1)
            btn = ttk.Button(self.frm_exist, text="Browse...",
                             command=lambda v=var, k=kind: self._browse_client(v, k))
            btn.grid(row=r, column=2, pady=1)
            self.exist_widgets += [ent, btn]
        ttk.Label(self.frm_exist, textvariable=self.var_fte_cfg, style="Muted.TLabel").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        # One hint line for both modes; wraps instead of widening the window.
        self.lbl_paths = ttk.Label(f, textvariable=self.var_paths, style="Muted.TLabel",
                                   justify="left")
        self.lbl_paths.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        f.bind("<Configure>", lambda e: self.lbl_paths.configure(
            wraplength=max(160, e.width - 24)))

        # Left: player + binds
        left = ttk.Frame(outer)
        left.grid(row=2, column=0, sticky="nsew", **pad)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        o = ttk.LabelFrame(left, text="Player and look", padding=6)
        o.grid(row=0, column=0, sticky="ew")
        ttk.Label(o, text="Player name:").grid(row=0, column=0, sticky="w")
        vcmd = (self.root.register(lambda s: len(s) <= MAX_NAME_LEN), "%P")
        self.ent_name = ttk.Entry(o, textvariable=self.var_name, width=28,
                                  validate="key", validatecommand=vcmd)
        self.ent_name.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Label(o, text="Look:").grid(row=1, column=0, sticky="w", pady=2)
        for c, (text, value) in enumerate(
                [("Software look", LOOK_SOFT), ("OpenGL look", LOOK_GL)], start=1):
            rb = ttk.Radiobutton(o, text=text, variable=self.var_look, value=value)
            rb.grid(row=1, column=c, sticky="w", padx=(0, 10))
            self.radios.append(rb)

        bframe = ttk.LabelFrame(left, text="Binds", padding=6)
        bframe.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        bframe.columnconfigure(0, weight=1)
        bframe.rowconfigure(0, weight=1)

        nb = ttk.Notebook(bframe)
        nb.grid(row=0, column=0, sticky="nsew")
        tab_qw = ttk.Frame(nb, padding=4)
        tab_mod = ttk.Frame(nb, padding=4)
        nb.add(tab_qw, text="Custom binds")
        nb.add(tab_mod, text="Mod binds")
        tab_qw.columnconfigure(0, weight=1)
        tab_qw.rowconfigure(1, weight=1)
        tab_mod.columnconfigure(0, weight=1)
        tab_mod.rowconfigure(0, weight=1)

        preset_row = ttk.Frame(tab_qw)
        preset_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(preset_row, text="Presets:").pack(side="left")
        btn_default = ttk.Button(preset_row, text="Default", width=9,
                                 command=lambda: self._apply_preset("vanilla"))
        btn_default.pack(side="left", padx=3)
        self.preset_buttons.append(btn_default)
        btn_clear = ttk.Button(preset_row, text="Clear", width=9, command=self._clear_binds)
        btn_clear.pack(side="left", padx=3)
        self.preset_buttons.append(btn_clear)
        ttk.Label(
            preset_row, style="Muted.TLabel",
            text="QuakeWorld controls + weapons"
        ).pack(side="left", padx=(8, 0))
        ttk.Label(tab_qw, text=BIND_HELP).grid(row=2, column=0, columnspan=2, sticky="w",
                                                pady=(4, 0))

        canvas = tk.Canvas(tab_qw, highlightthickness=0, height=260)
        self.canvases.append(canvas)
        sb = ttk.Scrollbar(tab_qw, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")
        inner = ttk.Frame(canvas)
        self._bind_inner = inner
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(_event=None):
            if canvas.winfo_reqwidth() < inner.winfo_reqwidth():
                canvas.configure(width=inner.winfo_reqwidth())  # never clip the ✕ column
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        mid = (len(cfg.BIND_ACTIONS) + 1) // 2
        label_w = max(18, max(len(a[2]) for a in cfg.BIND_ACTIONS) + 2)
        for i, (action_id, _cmd, label) in enumerate(cfg.BIND_ACTIONS):
            col = 0 if i < mid else 3
            row = i if i < mid else i - mid
            var = tk.StringVar(value="")
            self.bind_vars[action_id] = var
            ttk.Label(inner, text=label + ":", width=label_w, anchor="w").grid(
                row=row, column=col, sticky="w", padx=(0, 4), pady=1)
            box = KeyBox(inner, var, width=14)
            box.grid(row, col + 1, gap=16)
            self.bind_boxes.append(box)
        self._bind_canvas = canvas

        # Mod binds notebook (only mods with discovered custom actions)
        # Mod picker (combobox) + one scrollable page per mod: fits any number of
        # mods in a 1366x768 window and every field can be scrolled to.
        tab_mod.rowconfigure(1, weight=1)
        pick = ttk.Frame(tab_mod)
        pick.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(pick, text="Mod:").pack(side="left")
        self.var_mod_page = tk.StringVar()
        self.cmb_mod = ttk.Combobox(pick, textvariable=self.var_mod_page, state="readonly",
                                    width=24)
        self.cmb_mod.pack(side="left", padx=6)
        ttk.Label(pick, style="Muted.TLabel",
                  text="Saved to binds.cfg in the mod's folder.").pack(side="left")
        ttk.Label(tab_mod, text=BIND_HELP).grid(row=2, column=0, sticky="w", pady=(4, 0))
        pages_host = ttk.Frame(tab_mod)
        pages_host.grid(row=1, column=0, sticky="nsew")
        pages_host.columnconfigure(0, weight=1)
        pages_host.rowconfigure(0, weight=1)
        self.mod_pages = {}
        specs_by_key = {m["key"]: m for m in self.mod_specs}
        for mod_key in binds_mods.mods_with_bind_ui():
            spec = specs_by_key.get(mod_key) or {"title": mod_key, "clients": ["fte"]}
            short = _MOD_SHORT_TITLES.get(mod_key, spec.get("title", mod_key))
            tag = _clients_label(spec)
            tab_title = ("%s (%s)" % (short, tag)) if tag else short
            tab = ttk.Frame(pages_host)
            tab.grid(row=0, column=0, sticky="nsew")
            self.mod_pages[tab_title] = tab
            frame = self._scrollable(tab, height=150)
            self.mod_bind_vars[mod_key] = {}
            actions = binds_mods.actions_for(mod_key)
            # Two columns when a mod has many actions, so every field stays visible.
            per_col = (len(actions) + 1) // 2 if len(actions) > 8 else len(actions)
            for i, (action_id, _cmd, label) in enumerate(actions):
                r, c = 1 + (i % per_col), 3 * (i // per_col)
                var = tk.StringVar(value="")
                self.mod_bind_vars[mod_key][action_id] = var
                ttk.Label(frame, text=label + ":", anchor="w").grid(
                    row=r, column=c, sticky="w", padx=(0, 4), pady=1)
                box = KeyBox(frame, var, width=10)
                box.grid(r, c + 1, gap=10)
                self.bind_boxes.append(box)

        titles = list(self.mod_pages)
        self.cmb_mod.configure(values=titles)

        def _show_page(_e=None):
            self.mod_pages[self.var_mod_page.get()].tkraise()

        self.cmb_mod.bind("<<ComboboxSelected>>", _show_page)
        if titles:
            self.var_mod_page.set(titles[0])
            _show_page()

        # Right: included mods (always installed; informational only)
        m = ttk.LabelFrame(outer, text="Included mods", padding=6)
        m.grid(row=2, column=1, sticky="nsew", **pad)
        m.columnconfigure(0, weight=1)
        for r, spec in enumerate(self.mod_specs):
            ttk.Label(m, text=_mod_list_line(spec)).grid(
                row=r, column=0, sticky="w", pady=1)
        note_row = len(self.mod_specs)
        note = ttk.Label(
            m, style="Muted.TLabel", wraplength=280, justify="left",
            text="AirQuake, Quake Rally and FvF are FTE-only; the spray pack is "
                 "unezQuake-only."
        )
        note.grid(row=note_row, column=0, sticky="ew", pady=(8, 0))
        # Wrap to the panel's real width so the note never gets clipped.
        m.bind("<Configure>", lambda e, w=note: w.configure(
            wraplength=max(120, e.width - 24)))

        # Buttons (installer only — no Launch, no bats, no mods-only)
        b = ttk.Frame(outer)
        b.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.btn_install = ttk.Button(b, text="Install", command=self._start_install)
        self.btn_install.pack(side="left")
        self.btn_cfg = ttk.Button(b, text="Update configs only",
                                  command=lambda: self._start_install(configs_only=True))
        self.btn_cfg.pack(side="left", padx=6)
        self.btn_check = ttk.Button(b, text="Check for updates", command=self._start_check)
        self.btn_check.pack(side="left", padx=(0, 6))
        self.btn_cancel = ttk.Button(b, text="Cancel", command=self._cancel, state="disabled")
        self.btn_cancel.pack(side="left")
        self.btn_folder = ttk.Button(b, text="Open game folder", command=self._open_folder)
        self.btn_folder.pack(side="left", padx=6)
        self.btn_self = ttk.Button(b, text="Update installer", command=self._start_self_check)
        self.btn_self.pack(side="right")
        self.lbl_self = ttk.Label(b, textvariable=self.var_self, style="Link.TLabel")
        self.lbl_self.pack(side="right", padx=6)

        # Progress
        p = ttk.LabelFrame(outer, text="Progress", padding=6)
        p.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        p.columnconfigure(0, weight=1)
        p.rowconfigure(3, weight=1)
        ttk.Label(p, textvariable=self.var_status).grid(row=0, column=0, sticky="w")
        self.pb_file = ttk.Progressbar(p, mode="determinate", maximum=100)
        self.pb_file.grid(row=1, column=0, sticky="ew", pady=2)
        self.pb_total = ttk.Progressbar(p, mode="determinate", maximum=100)
        self.pb_total.grid(row=2, column=0, sticky="ew", pady=2)
        txt_frame = ttk.Frame(p)
        txt_frame.grid(row=3, column=0, sticky="nsew", pady=(4, 0))
        txt_frame.columnconfigure(0, weight=1)
        txt_frame.rowconfigure(0, weight=1)
        self.txt = tk.Text(txt_frame, height=8, wrap="word", state="disabled",
                           font=("Consolas", 9) if IS_WINDOWS else ("TkFixedFont", 9))
        self.txt.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(txt_frame, command=self.txt.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=sb2.set)
        self._recolor()

    # --------------------------------------------------------------- settings
    def _assets_dir(self, *parts):
        base = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "quake_installer", "assets")
        return os.path.join(base, *parts)

    def _gear_image(self):
        """Nearest-size gear icon for the current theme (None if assets are missing)."""
        dark = self._theme_key() == "sv-dark"
        folder = self._assets_dir("icons")
        try:
            sizes = sorted(int(f.rsplit("-", 1)[1][:-4]) for f in os.listdir(folder)
                           if f.startswith("gear-") and f.endswith(".png"))
        except OSError:
            return None
        if not sizes:
            return None
        try:
            scale = float(self.root.tk.call("tk", "scaling")) / 1.333
        except Exception:
            scale = 1.0
        want = max(14, min(40, int(round(18 * scale))))
        best = min(sizes, key=lambda s: abs(s - want))
        key = (dark, best)
        if key not in self._gear_cache:
            try:
                self._gear_cache[key] = tk.PhotoImage(
                    master=self.root, file=os.path.join(
                        folder, "gear-%s-%d.png" % ("dark" if dark else "light", best)))
            except tk.TclError:
                return None
        return self._gear_cache[key]

    def _update_gear_image(self):
        btn = getattr(self, "btn_settings", None)
        if btn is None:
            return
        img = self._gear_image()
        if img is None:
            btn.configure(image="", text="Settings", compound="left")
        else:
            btn.configure(image=img, text="")

    def _open_settings(self):
        if self.worker and self.worker.is_alive():
            return
        old = self.settings_window
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except tk.TclError:
            pass
        from .settings_dialog import SettingsDialog
        self.settings_dialog = SettingsDialog(self)
        self.settings_window = self.settings_dialog.win

    # ----------------------------------------------------------------- theme
    def _theme_key(self):
        name = self.var_theme.get()
        for k, label in THEMES:
            if label == name or k == name:
                return k
        return "classic"

    def _circle_img(self, size, fill, ring):
        img = tk.PhotoImage(master=self.root, width=size + 7, height=size)
        c = (size - 1) / 2.0
        r = size / 2.0 - 0.5
        rows = []
        for y in range(size):
            row = []
            for x in range(size):
                d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
                if d <= r - 1.6:
                    row.append(fill)
                elif d <= r:
                    row.append(ring)
                else:
                    row.append(None)
            rows.append(row)
        for y, row in enumerate(rows):
            for x, col in enumerate(row):
                if col:
                    img.put(col, (x, y))
        return img

    def _win7_radio_imgs(self, size):
        base = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "quake_installer", "assets", "radio")
        sizes = sorted(int(f.rsplit("_", 1)[1][:-4]) for f in os.listdir(base)
                       if f.startswith("radio_selected_") and f.endswith(".png"))
        best = min(sizes, key=lambda s: abs(s - size))
        return [tk.PhotoImage(master=self.root, file=os.path.join(
            base, "radio_%s_%d.png" % (st, best)))
            for st in ("selected", "unselected", "hover", "disabled")]

    def _ensure_dark_radio(self, style, pal):
        theme = style.theme_use()
        done = getattr(self, "_dark_radio_themes", set())
        if theme in done:
            return
        size = 18
        try:
            size = max(14, int(round(18 * float(self.root.tk.call("tk", "scaling")) / 1.333)))
        except Exception:
            pass
        imgs = getattr(self, "_radio_imgs", [])
        # Windows 7 style bubbles, pre-rendered by tools/render_radios.py.
        try:
            on, off, hov, dis = self._win7_radio_imgs(size)
        except Exception:
            on = self._circle_img(size, pal["accent"], pal["accent"])
            off = self._circle_img(size, None, "#9a9a9a")
            hov = self._circle_img(size, None, "#ffffff")
            dis = self._circle_img(size, None, "#555555")
        imgs += [on, off, hov, dis]
        self._radio_imgs = imgs
        style.element_create("Bqi.Radio.indicator", "image", off,
                             ("disabled", dis), ("selected", on),
                             ("active", hov), sticky="")
        style.layout("Bqi.TRadiobutton", [
            ("Radiobutton.padding", {"sticky": "nswe", "children": [
                ("Bqi.Radio.indicator", {"side": "left", "sticky": ""}),
                ("Radiobutton.label", {"side": "left", "sticky": "nswe"})]})])
        style.configure("Bqi.TRadiobutton", padding=(0, 2, 6, 2))
        done.add(theme)
        self._dark_radio_themes = done

    def _apply_theme(self, save=False):
        key = self._theme_key()
        style = ttk.Style()
        if key.startswith("sv-"):
            sv = _load_sv_ttk()
            try:
                if sv is None:
                    raise ImportError("sv_ttk not available")
                sv.set_theme("dark" if key == "sv-dark" else "light", self.root)
            except Exception as exc:  # never fail the app over a theme
                self._log("WARN: Sun Valley theme unavailable (%s); using Classic" % exc)
                key = "classic"
                self.var_theme.set(THEMES[0][1])
        if key == "classic":
            try:
                style.theme_use(self.classic_theme)
            except tk.TclError:
                pass
            self._undo_sv_palette()
        style.configure("Clear.TButton", padding=(2, 0))
        self._recolor()
        self._update_gear_image()
        if save:
            settings.update(theme=key)

    def _undo_sv_palette(self):
        """sv_ttk calls tk_setPalette and restyles '.', and Tk keeps those colours
        after switching back. Re-apply the Classic palette and root style."""
        if not getattr(self.root, "_sv_ttk_loaded", False):
            return
        style = ttk.Style()
        saved = dict(self.classic_style or {})
        self.root.tk.call("tk_setPalette", saved.get("background", "#d9d9d9"))
        if saved:
            style.configure(".", **saved)

    def _recolor(self):
        dark = self._theme_key() == "sv-dark"
        pal = PALETTES["dark" if dark else "light"]
        KeyBox.pal = pal
        style = ttk.Style()
        style.configure("Muted.TLabel", foreground=pal["muted"])
        style.configure("Link.TLabel", foreground=pal["link"])
        # Dark: Windows 7 style radio bubbles (glossy blue dot); text unchanged.
        style.map("TRadiobutton", foreground=[], font=[])
        rstyle = "TRadiobutton"
        if dark:
            try:
                self._ensure_dark_radio(style, pal)
                rstyle = "Bqi.TRadiobutton"
            except tk.TclError:
                rstyle = "TRadiobutton"
        for rb in getattr(self, "mode_radios", []) + getattr(self, "radios", []):
            try:
                rb.configure(style=rstyle)
            except tk.TclError:
                pass
        bg = style.lookup("TFrame", "background") or None
        for c in self.canvases:
            try:
                if bg:
                    c.configure(background=bg)
            except tk.TclError:
                pass
        if hasattr(self, "txt"):
            self.txt.configure(background=pal["text_bg"], foreground=pal["fg"],
                               insertbackground=pal["fg"])
            for tag in ("err", "ok", "warn"):
                self.txt.tag_configure(tag, foreground=pal[tag])
        for kb in KeyBox.instances:
            try:
                kb.recolor()
            except tk.TclError:
                pass

    # ----------------------------------------------------------------- helpers
    def _scrollable(self, parent, height=200):
        """Canvas + scrollbar in parent; returns the inner frame (mouse wheel scrolls)."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = tk.Canvas(parent, highlightthickness=0, height=height)
        self.canvases.append(canvas)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        inner = ttk.Frame(canvas, padding=4)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _cfg(_e=None):
            if canvas.winfo_reqwidth() < inner.winfo_reqwidth():
                canvas.configure(width=inner.winfo_reqwidth())  # never clip the ✕ column
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win, width=canvas.winfo_width())

        inner.bind("<Configure>", _cfg)
        canvas.bind("<Configure>", _cfg)

        def _wheel(e):
            if getattr(e, "num", None) == 4:
                canvas.yview_scroll(-2, "units")
            elif getattr(e, "num", None) == 5:
                canvas.yview_scroll(2, "units")
            else:
                canvas.yview_scroll(int(-e.delta / (120 if IS_WINDOWS else 1)) or
                                    (-1 if e.delta > 0 else 1), "units")

        def _enter(_e):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel)
            canvas.bind_all("<Button-5>", _wheel)

        def _leave(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)
        return inner

    def _settings_values(self):
        values = {
            "player_name": self.var_name.get(),
            "look": self.var_look.get(),
            "binds": {k: v.get() for k, v in self.bind_vars.items() if v.get().strip()},
            "mod_binds": {mk: {a: v.get() for a, v in mv.items() if v.get().strip()}
                          for mk, mv in self.mod_bind_vars.items()},
            "check_installer_updates": bool(self.var_self_auto.get()),
            "install_mode": self.var_mode.get(),
            "theme": self._theme_key(),
            # Engine choice is always kept; folder values only when the user
            # wants them remembered (off = defaults next start).
            "remember_dirs": bool(self.var_remember_dirs.get()),
            "install_unez": bool(self.var_install_unez.get()),
            "install_fte": bool(self.var_install_fte.get()),
        }
        if values["remember_dirs"]:
            values.update({
                "root": self.var_root.get().strip(),
                "unez_path": self.var_unez.get().strip(),
                "fte_path": self.var_fte.get().strip(),
                "fte_cfg_choice": dict(self.fte_cfg_choice),
                "unez_install_path": self.var_unez_target.get().strip(),
                "fte_install_path": self.var_fte_target.get().strip(),
            })
        return values

    def _load_settings(self):
        """Last-used settings, or the Default preset on first run."""
        data = settings.load()
        if data and data.get("check_installer_updates") is False:
            self.var_self_auto.set(False)
        if data:
            remember = data.get("remember_dirs", True) is not False
            self.var_remember_dirs.set(remember)
            self.var_install_unez.set(data.get("install_unez", True) is not False)
            self.var_install_fte.set(data.get("install_fte", True) is not False)
            if data.get("install_mode") in (MODE_FULL, MODE_EXISTING):
                self.var_mode.set(data["install_mode"])
            if remember:
                self.var_unez_target.set(data.get("unez_install_path") or "")
                self.var_fte_target.set(data.get("fte_install_path") or "")
                self.var_unez.set(data.get("unez_path") or "")
                self.var_fte.set(data.get("fte_path") or "")
                if isinstance(data.get("fte_cfg_choice"), dict):
                    self.fte_cfg_choice = dict(data["fte_cfg_choice"])
                if data.get("root"):
                    self.var_root.set(data["root"])
            for k, label in THEMES:
                if data.get("theme") == k:
                    self.var_theme.set(label)
            if self._theme_key() != "classic":
                self._apply_theme()
        if not data:
            self._apply_preset("vanilla")
            self._log("First run: binds filled from the Default preset (stock default.cfg).")
            return
        if data.get("player_name"):
            self.var_name.set(data["player_name"][:MAX_NAME_LEN])
        if data.get("look") in (LOOK_SOFT, LOOK_GL):
            self.var_look.set(data["look"])
        for k, v in (data.get("binds") or {}).items():
            if k in self.bind_vars:
                self.bind_vars[k].set(v)
        for mk, mv in (data.get("mod_binds") or {}).items():
            for a, v in (mv or {}).items():
                if mk in self.mod_bind_vars and a in self.mod_bind_vars[mk]:
                    self.mod_bind_vars[mk][a].set(v)
        self._log("Loaded your last settings from %s" % settings.settings_path())

    def _update_paths(self):
        self.var_paths.set(paths_hint(
            self._existing_mode(), self.var_root.get(),
            install_unez=bool(self.var_install_unez.get()),
            install_fte=bool(self.var_install_fte.get()),
            unez_target=self.var_unez_target.get(),
            fte_target=self.var_fte_target.get(),
            unez_path=self.var_unez.get(),
            fte_path=self.var_fte.get()))

    def _existing_mode(self):
        return self.var_mode.get() == MODE_EXISTING

    def _show_mode(self):
        self._update_paths()
        if self._existing_mode():
            self.frm_full.grid_remove()
            self.frm_exist.grid()
            self.frm_install.configure(text="Pick the folder for each client you have")
        else:
            self.frm_exist.grid_remove()
            self.frm_full.grid()
            self.frm_install.configure(text="Install folder")

    def _browse_client(self, var, kind):
        start = var.get() if os.path.isdir(var.get()) else None
        d = filedialog.askdirectory(
            title="Choose your existing %s folder" % ("unezQuake" if kind == "unez" else "FTE"),
            initialdir=start, mustexist=True)
        if not d:
            return
        d = os.path.normpath(d)
        var.set(d)
        check = existing_mod.check_unez_folder if kind == "unez" else existing_mod.check_fte_folder
        warn = check(d)
        if warn:
            self._log("WARN: " + "; ".join(warn))
            messagebox.showwarning(APP_TITLE, "This doesn't look like a %s folder:\n\n%s\n\n"
                                   "You can still use it if you're sure."
                                   % ("unezQuake" if kind == "unez" else "FTE",
                                      "\n".join(warn)))

    def _fte_detect(self):
        d = self.var_fte.get().strip()
        if not d or not os.path.isdir(d):
            return None
        return existing_mod.detect_fte_config(d)

    def _update_fte_cfg(self):
        d = self.var_fte.get().strip()
        if not d:
            self.var_fte_cfg.set(
                "No FTE folder chosen, so mods will only go into unezQuake."
                if self.var_unez.get().strip() else "")
            return
        if not self.var_unez.get().strip():
            self.var_fte_cfg.set(
                "No unezQuake folder chosen, so mods will only go into FTE.")
            return
        det = self._fte_detect()
        if det is None:
            self.var_fte_cfg.set("FTE folder not found yet.")
            return
        choice = self.fte_cfg_choice.get(os.path.normcase(d))
        if det.mode == existing_mod.MODE_ASK and choice:
            where = det.home if choice == "home" else d
            self.var_fte_cfg.set("FTE configs: %s  (your choice)" % where)
        else:
            self.var_fte_cfg.set(det.describe())

    def _resolve_fte_cfg_dir(self, fte_dir):
        """Effective FTE cfg dir; asks when detection is ambiguous. None = cancelled."""
        det = existing_mod.detect_fte_config(fte_dir)
        key = os.path.normcase(fte_dir)
        if det.mode == existing_mod.MODE_ASK:
            choice = self.fte_cfg_choice.get(key)
            if not choice:
                ans = messagebox.askyesnocancel(
                    APP_TITLE,
                    "Which folder does your FTE save its configs in?\n\n%s\n\n"
                    "Yes = home folder:\n  %s\n\nNo = FTE install folder:\n  %s"
                    % (det.reason, det.home, fte_dir))
                if ans is None:
                    return None
                choice = "home" if ans else "install"
                self.fte_cfg_choice[key] = choice
            out = det.home if choice == "home" else fte_dir
        else:
            out = det.write_root
        self._log("FTE config location: %s (%s)" % (out, det.reason))
        self._update_fte_cfg()
        return out

    def _apply_preset(self, name):
        preset = cfg.PRESETS.get(name) or {}
        if name == "vanilla":
            for action_id in self.bind_vars:
                self.bind_vars[action_id].set(preset.get(action_id, ""))
            return
        if name == "wasd":
            for action_id, key in preset.items():
                self.bind_vars[action_id].set(key)
            return
        if name == "modern":
            for action_id, key in preset.items():
                if action_id in self.bind_vars:
                    self.bind_vars[action_id].set(key)

    def _clear_binds(self):
        for var in self.bind_vars.values():
            var.set("")
        for mvars in self.mod_bind_vars.values():
            for var in mvars.values():
                var.set("")

    def _collect_binds(self):
        raw = {aid: var.get() for aid, var in self.bind_vars.items()}
        return cfg.clean_binds(raw)

    def _collect_mod_binds(self):
        out = {}
        for mod_key, mvars in self.mod_bind_vars.items():
            raw = {aid: var.get() for aid, var in mvars.items()}
            cleaned = binds_mods.clean_mod_binds(mod_key, raw)
            if cleaned:
                out[mod_key] = cleaned
        return out

    def _browse(self):
        start = self.var_root.get() if os.path.isdir(self.var_root.get()) else None
        d = filedialog.askdirectory(title="Choose install root", initialdir=start,
                                    mustexist=False)
        if d:
            self.var_root.set(os.path.normpath(d))

    def _log(self, msg):
        tag = None
        s = msg.strip()
        if s.startswith("ERROR") or s.startswith("FAIL"):
            tag = "err"
        elif s.startswith("OK") or s.startswith("INSTALL COMPLETE"):
            tag = "ok"
        elif s.startswith("WARN"):
            tag = "warn"
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n", tag)
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _set_busy(self, busy):
        st = "disabled" if busy else "normal"
        widgets = ([self.ent_root, self.btn_browse, self.ent_name, self.btn_install,
                    self.btn_cfg, self.btn_check, self.btn_self, self.btn_settings] +
                   self.mode_radios + self.exist_widgets +
                   self.radios + self.bind_entries + self.preset_buttons)
        for w in widgets:
            w.configure(state=st)
        for box in self.bind_boxes:
            box.set_enabled(not busy)
        self.btn_cancel.configure(state="normal" if busy else "disabled")

    # --------------------------------------------------------------- actions
    def _norm_install_target(self, text, label):
        """Settings folder override: None when blank, else a validated full path."""
        p = folders.clean(text)
        if not p:
            return None
        p = os.path.normpath(p)
        if not folders.is_full_path(p):
            raise ValueError("Enter a full %s folder path, e.g. %s." % (
                label, ("C:\\Games\\" if IS_WINDOWS else "~/Games/") + label))
        return p

    def _collect(self, configs_only, allow_empty_name=False):
        if self._existing_mode():
            return self._collect_existing(configs_only, allow_empty_name)
        root = folders.clean(self.var_root.get())
        if not root:
            raise ValueError("Please choose an install folder.")
        if not folders.is_full_path(root):
            raise ValueError("Please enter a full path, e.g. %s"
                             % ("C:\\Games" if IS_WINDOWS else "~/Games"))
        name = self.var_name.get()
        if not name.strip() and not allow_empty_name:
            raise ValueError("Please enter a player name.")
        name = name if name.strip() else "player"
        if not self.var_install_unez.get() and not self.var_install_fte.get():
            raise ValueError("Choose at least one engine in Settings (unezQuake or FTE).")
        try:
            binds = self._collect_binds()
        except ValueError as exc:
            raise ValueError("Invalid key in binds: %s" % exc)
        # Always install every configured mod (no checkboxes).
        try:
            mod_binds = self._collect_mod_binds()
        except ValueError as exc:
            raise ValueError("Invalid key in mod binds: %s" % exc)
        opts = Options(root=root, player_name=name, look=self.var_look.get(),
                       binds=binds, write_bats=False, configs_only=configs_only,
                       mods=None, mod_files={}, mods_only=False, mod_binds=mod_binds,
                       platform=self.platform,
                       install_unez=bool(self.var_install_unez.get()),
                       install_fte=bool(self.var_install_fte.get()),
                       unez_target=self._norm_install_target(
                           self.var_unez_target.get(), "ezquake"),
                       fte_target=self._norm_install_target(
                           self.var_fte_target.get(), "FTE"))
        # Same rules the installer enforces; checked here so the message shows
        # before anything starts.
        opts.use_manifest_dirs()
        folders.check_engine_folders(opts.root, opts.unez_dir, opts.fte_dir)
        return opts

    def _collect_existing(self, configs_only, allow_empty_name=False):
        paths = {}
        for kind, var in (("unez", self.var_unez), ("fte", self.var_fte)):
            p = os.path.expanduser(var.get().strip().strip('"'))
            if p and not os.path.isdir(p):
                raise ValueError("%s folder does not exist:\n%s"
                                 % ("unezQuake" if kind == "unez" else "FTE", p))
            paths[kind] = os.path.normpath(p) if p else None
        if not paths["unez"] and not paths["fte"]:
            raise ValueError("Choose your existing unezQuake folder and/or FTE folder.")
        folders.check_existing_folders(paths["unez"], paths["fte"])
        name = self.var_name.get()
        if not name.strip() and not allow_empty_name:
            raise ValueError("Please enter a player name.")
        name = name if name.strip() else "player"
        try:
            binds = self._collect_binds()
            mod_binds = self._collect_mod_binds()
        except ValueError as exc:
            raise ValueError("Invalid key in binds: %s" % exc)
        fte_cfg = None
        if paths["fte"]:
            fte_cfg = self._resolve_fte_cfg_dir(paths["fte"])
            if fte_cfg is None:
                raise ValueError("Cancelled: FTE config location not chosen.")
        return Options(root=paths["unez"] or paths["fte"], player_name=name,
                       look=self.var_look.get(), binds=binds, configs_only=configs_only,
                       mods=None, mod_binds=mod_binds, platform=self.platform,
                       existing=True, unez_path=paths["unez"], fte_path=paths["fte"],
                       fte_cfg_dir=fte_cfg)

    # ---------------------------------------------------------- updates
    def _start_check(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            opts = self._collect(True, allow_empty_name=True)
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        from . import updater
        note = "" if opts.existing else updater.platform_mismatch_note(opts.root, opts.platform)
        if note:
            self._log("NOTE: " + note)
            messagebox.showinfo(APP_TITLE, note)
        if not os.path.isdir(opts.root):
            messagebox.showinfo(APP_TITLE, "Nothing installed at %s yet. Run Install first."
                                % opts.root)
            return
        self.last_opts = opts
        self.cancel_event.clear()
        self._set_busy(True)
        self._log("=" * 60)
        self._log("Checking for updates (%s builds)..." % PLATFORM_LABELS[self.platform])
        self.var_status.set("Checking for updates...")
        self.worker = threading.Thread(target=self._check_worker, args=(opts,), daemon=True)
        self.worker.start()

    def _check_worker(self, opts):
        from . import updater
        rep = QueueReporter(self.q)
        try:
            items = updater.check_updates(opts.root, opts.platform, log=rep.log, opts=opts)
            self.q.put(("checked", items))
        except Exception as exc:
            self.q.put(("error", "Update check failed: %s" % exc))

    def _show_updates(self, items):
        # Every installable component gets a checkbox, presets cover
        # "all / engines / mods", and only the checked subset is applied.
        self._set_busy(False)
        from . import updater
        headline, summary_lines = updater.check_summary(items)
        opts = self.last_opts
        off = updater.turned_off_notes(opts.root, opts) if opts is not None else []
        summary_lines = list(summary_lines) + off
        for line in off:
            self._log("NOTE: " + line)
        for i in items:
            tag = "WARN: " if i.needs_update or i.status not in ("up to date",) else "OK  "
            self._log(tag + i.line())
        self.var_status.set(headline)
        old = self.update_window
        if old is not None and old.winfo_exists():
            old.destroy()
        win = tk.Toplevel(self.root)
        win.title("Check for updates")
        win.transient(self.root)
        win.bind("<Escape>", lambda _e: win.destroy())
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, font=("TkDefaultFont", 10, "bold"),
                  text=headline).pack(anchor="w")
        for line in summary_lines:
            ttk.Label(frm, style="Muted.TLabel", text=line, wraplength=760,
                      justify="left").pack(anchor="w", pady=(2, 0))
        rows_frame = ttk.Frame(frm)
        rows_frame.pack(fill="both", expand=True, pady=6)
        inner = self._scrollable(rows_frame, height=min(14, max(3, len(items))) * 22)
        default_ids = updater.select_components(items)
        engine_ids = updater.select_components(items, updater.SELECT_MODE_ENGINES)
        mod_ids = updater.select_components(items, updater.SELECT_MODE_MODS)
        row_vars = []
        selectable = 0
        for r, item in enumerate(items):
            can = updater.is_selectable(item)
            selectable += 1 if can else 0
            var = tk.BooleanVar(value=can and item.component in default_ids)
            chk = ttk.Checkbutton(inner, text=item.title, variable=var,
                                  command=lambda: _refresh(),
                                  state="normal" if can else "disabled")
            chk.grid(row=r, column=0, sticky="w", padx=(2, 8), pady=1)
            ttk.Label(inner, text=item.status, width=26, anchor="w").grid(
                row=r, column=1, sticky="w", padx=(0, 8))
            ttk.Label(inner, text=item.detail, style="Muted.TLabel",
                      wraplength=340, justify="left").grid(row=r, column=2, sticky="w")
            row_vars.append((item, var, can))
        inner.columnconfigure(0, weight=1)
        ttk.Label(frm, style="Muted.TLabel", wraplength=760, justify="left",
                  text="Update replaces engine files and mod paks only; your cfgs "
                       "(autoexec/binds/config.cfg, default.fmf) are kept. "
                       "Tick the components to install, then Update selected."
                  ).pack(anchor="w")

        def _checked():
            return [it for it, var, can in row_vars if can and var.get()]

        def _refresh():
            n = len(_checked())
            btn_update.configure(text="Update selected (%d)" % n,
                                 state="normal" if n else "disabled")
            lbl_sel.configure(text="%d of %d component(s) selected" % (n, selectable))

        def _preset(mode):
            want = updater.select_components(items, mode)
            for it, var, can in row_vars:
                var.set(can and it.component in want)
            _refresh()

        def _apply():
            chosen = _checked()
            if not chosen:
                return
            win.destroy()
            self._start_update(chosen)

        lbl_sel = ttk.Label(frm, style="Muted.TLabel")
        lbl_sel.pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Select all",
                   command=lambda: _preset(updater.SELECT_MODE_ALL)).pack(side="left")
        ttk.Button(bar, text="Deselect all",
                   command=lambda: _preset(updater.SELECT_MODE_NONE)).pack(
            side="left", padx=(6, 0))
        ttk.Button(bar, text="Engine only", state="normal" if engine_ids else "disabled",
                   command=lambda: _preset(updater.SELECT_MODE_ENGINES)).pack(
            side="left", padx=(18, 0))
        ttk.Button(bar, text="Mods only", state="normal" if mod_ids else "disabled",
                   command=lambda: _preset(updater.SELECT_MODE_MODS)).pack(
            side="left", padx=(6, 0))
        btn_update = ttk.Button(bar, text="Update selected (0)", state="disabled",
                                command=_apply)
        btn_update.pack(side="right")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right", padx=6)
        _refresh()
        center_window(win, self.root)
        self.update_window = win

    def _start_update(self, items):
        opts = self.last_opts
        self.cancel_event.clear()
        self._set_busy(True)
        self._log("Updating %d component(s)..." % len([i for i in items if i.needs_update]))
        self.worker = threading.Thread(target=self._update_worker, args=(opts, items),
                                       daemon=True)
        self.worker.start()

    def _update_worker(self, opts, items):
        from . import updater
        rep = QueueReporter(self.q)
        try:
            up, failed = updater.apply_updates(opts, items, rep, self.cancel_event)
            self.q.put(("updated", (up, failed)))
        except Cancelled:
            self.q.put(("cancelled", None))
        except Exception as exc:
            self.q.put(("error", "Update failed: %s" % exc))

    # ------------------------------------------------------ installer self-update
    def _start_self_check(self, quiet=False):
        if (self.self_worker and self.self_worker.is_alive()) or \
                (self.worker and self.worker.is_alive()):
            return
        if not quiet:
            self.var_status.set("Checking for a new version of the installer...")
        self.self_worker = threading.Thread(target=self._self_check_worker, args=(quiet,),
                                            daemon=True)
        self.self_worker.start()

    def _self_check_worker(self, quiet):
        res = selfupdate.check(timeout=8 if quiet else 15)
        self.q.put(("selfcheck", (quiet, res)))

    def _show_self_check(self, quiet, res):
        if quiet:  # startup check: a small notice only, never a popup
            if res.status == selfupdate.STATUS_UPDATE:
                self.var_self.set("Installer %s is available" % res.release.version)
            return
        self.var_status.set(res.message)
        if res.status == selfupdate.STATUS_ERROR:
            self._log("WARN: installer update check: " + res.message)
            messagebox.showwarning(APP_TITLE, res.message)
            return
        if res.status != selfupdate.STATUS_UPDATE:
            self.var_self.set("")
            messagebox.showinfo(APP_TITLE, res.message)
            return
        rel = res.release
        self.var_self.set("Installer %s is available" % rel.version)
        win = tk.Toplevel(self.root)
        win.title("Update installer")
        win.transient(self.root)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, font=("TkDefaultFont", 10, "bold"),
                  text="Based Quake Installer %s is available. You have %s."
                       % (rel.version, __version__)).pack(anchor="w")
        if rel.notes:
            ttk.Label(frm, text="What's new:").pack(anchor="w", pady=(8, 0))
            ttk.Label(frm, text=rel.notes, justify="left", wraplength=520).pack(
                anchor="w", padx=(8, 0))
        ttk.Label(frm, style="Muted.TLabel", wraplength=520, justify="left",
                  text="This updates the installer program only. Your games, mods and "
                       "configs are not touched.").pack(anchor="w", pady=(10, 0))
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Later", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="Update now",
                   command=lambda: (win.destroy(), self._start_self_update(rel))
                   ).pack(side="right", padx=6)
        center_window(win, self.root)
        self.self_window = win

    def _start_self_update(self, rel):
        if self.worker and self.worker.is_alive():
            return
        self.cancel_event.clear()
        self._set_busy(True)
        self._step = (1, 1)
        self.pb_file["value"] = self.pb_total["value"] = 0
        self._log("=" * 60)
        self._log("Updating the installer to %s..." % rel.version)
        self.var_status.set("Updating the installer...")
        self.worker = threading.Thread(target=self._self_update_worker, args=(rel,),
                                       daemon=True)
        self.worker.start()

    def _self_update_worker(self, rel):
        rep = QueueReporter(self.q)
        try:
            out = selfupdate.perform(rel, progress=rep.progress, cancel_event=self.cancel_event,
                                     log=rep.log)
        except Cancelled:
            self.q.put(("cancelled", None))
            return
        except Exception as exc:
            out = selfupdate.Outcome(url=rel.html_url, message="The update didn't work: %s"
                                     "\n\nOpening the release page instead." % exc)
        self.q.put(("selfupdated", out))

    def _finish_self_update(self, out):
        self._set_busy(False)
        if out.restart_cmd:
            self._log("OK  " + out.message + " Restarting...")
            self.var_status.set(out.message + " Restarting...")
            messagebox.showinfo(APP_TITLE, out.message + "\n\nThe installer will now restart.")
            try:
                import subprocess
                subprocess.Popen(out.restart_cmd, env=selfupdate.restart_env(),
                                 cwd=os.path.dirname(out.restart_cmd[-1]) or None)
            except OSError as exc:
                messagebox.showwarning(APP_TITLE, "Updated, but couldn't restart (%s). "
                                       "Start the installer again yourself." % exc)
            self.root.destroy()
            return
        self._log("WARN: " + out.message.replace("\n", " "))
        self.var_status.set("Installer not updated.")
        messagebox.showinfo(APP_TITLE, out.message)
        if out.url:
            import webbrowser
            webbrowser.open(out.url)

    def _start_install(self, configs_only=False):
        if self.worker and self.worker.is_alive():
            return
        try:
            opts = self._collect(configs_only)
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        if not opts.binds and not any(self._collect_mod_binds().values()):
            if not messagebox.askyesno(
                    APP_TITLE, "Every bind field is blank.\n\nWrite a config with NO key "
                    "binds (unbindall, nothing bound)?\n\nChoose No, then click Default to "
                    "fill the stock binds."):
                return
        settings.save(self._settings_values())
        if '"' in opts.player_name:
            self._log("Note: double quotes in the player name are written as ' "
                      "(Quake cannot escape \" inside a cfg string).")
        self.last_opts = opts
        self.cancel_event.clear()
        self.pb_file["value"] = 0
        self.pb_total["value"] = 0
        self._set_busy(True)
        self._log("=" * 60)
        self._log("Starting %s..." % ("config update" if configs_only else
                                      "mods-only install (your clients are not changed)"
                                      if opts.existing else "install (engines + all mods)"))
        self.worker = threading.Thread(target=self._worker, args=(opts,), daemon=True)
        self.worker.start()

    def _worker(self, opts):
        rep = QueueReporter(self.q)
        try:
            res = run_install(opts, rep, self.cancel_event)
            self.q.put(("done", res))
        except Cancelled:
            self.q.put(("cancelled", None))
        except InstallError as exc:
            self.q.put(("error", str(exc)))
        except Exception as exc:
            self.q.put(("error", "Unexpected error: %s\n%s" % (exc, traceback.format_exc())))

    def _cancel(self):
        self.cancel_event.set()
        self.var_status.set("Cancelling...")

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._log(data)
                elif kind == "step":
                    i, total, title = data
                    self._step = (i, total)
                    self.var_status.set("Step %d of %d: %s" % (i, total, title))
                    self._log("==> " + title)
                    self.pb_total["value"] = (i - 1) * 100.0 / total
                    self.pb_file["value"] = 0
                elif kind == "progress":
                    done, total = data
                    i, steps = self._step
                    if total:
                        frac = min(1.0, float(done) / total)
                        self.pb_file.configure(mode="determinate")
                        self.pb_file["value"] = frac * 100
                        self.pb_total["value"] = (i - 1 + frac) * 100.0 / steps
                        self.var_status.set("Step %d of %d: %s / %s" % (
                            i, steps, _fmt_bytes(done), _fmt_bytes(total)))
                    else:
                        self.pb_file["value"] = (self.pb_file["value"] + 2) % 100
                        self.var_status.set("Step %d of %d: %s" % (i, steps, _fmt_bytes(done)))
                elif kind == "done":
                    self._finish_ok(data)
                elif kind == "selfcheck":
                    self._show_self_check(*data)
                elif kind == "selfupdated":
                    self._finish_self_update(data)
                elif kind == "checked":
                    self._show_updates(data)
                elif kind == "updated":
                    up, failed = data
                    self._set_busy(False)
                    self.pb_file["value"] = self.pb_total["value"] = 100
                    for i in up:
                        self._log("OK  updated %s" % i.title)
                    for i, msg in failed:
                        self._log("WARN: %s not updated: %s" % (i.title, msg))
                    self.var_status.set("Update finished: %d updated, %d failed."
                                        % (len(up), len(failed)))
                elif kind == "error":
                    self._set_busy(False)
                    self.var_status.set("Failed.")
                    self._log("ERROR: " + data)
                    messagebox.showerror(APP_TITLE, "Install failed:\n\n" + data.split("\n")[0]
                                         + ("\n\nSee the log for details." if "\n" in data else ""))
                elif kind == "cancelled":
                    self._set_busy(False)
                    self.var_status.set("Cancelled.")
                    self._log("WARN: cancelled by user")
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _finish_ok(self, res):
        self.result = res
        self._set_busy(False)
        self.pb_file["value"] = 100
        self.pb_total["value"] = 100
        self.var_status.set("Done.")
        o = self.last_opts
        self._log("")
        self._log("INSTALL COMPLETE" if not o.configs_only
                  else "INSTALL COMPLETE (configs updated)")
        if o.existing:
            self._log("  Mods only: client programs and their settings were not changed.")
            if o.fte_dir:
                self._log("  FTE configs: %s" % o.fte_cfg_root)
        for label, d, exe in (("UnezQuake", o.unez_dir, res.unez_exe),
                              ("FTE      ", o.fte_dir, res.fte_exe)):
            self._log("  %s : %s" % (label, os.path.join(d, exe or "?") if d else "(skipped)"))
        if res.fte_source:
            self._log("  FTE pkg   : %s" % res.fte_source)
        if res.fte_fmf:
            self._log("  FTE fmf   : %s (DISABLEHOMEDIR)" % res.fte_fmf)
        for item in res.mods_installed:
            key, title, gd, src = item[0], item[1], item[2], item[3]
            clients = item[4] if len(item) > 4 else ["fte"]
            self._log("OK  mod %s -> %s%s%s  [%s]" % (title, "+".join(clients), os.sep, gd, src))
        for key, title, msg in res.mods_failed:
            self._log("WARN: mod %s NOT installed: %s" % (title, msg))
        for w in res.warnings:
            self._log("WARN: " + w)
        self._log("  Only shareware pak0.pak is installed. Copy your own pak1.pak into each "
                  "id1 folder that needs registered Quake.")
        if not o.existing and o.fte_dir:
            self._log("  FTE: run the exe from the FTE folder — default.fmf DISABLEHOMEDIR "
                      "replaces needing -nohome on the command line.")

    def _open_folder(self):
        if self._existing_mode():
            paths = [p for p in (self.var_unez.get().strip(), self.var_fte.get().strip()) if p]
            det = self._fte_detect()
            if det is not None and det.write_root and \
                    os.path.normcase(det.write_root) != os.path.normcase(det.install):
                paths.append(det.write_root)  # FTE home dir (where its cfgs are)
            paths = [p for p in paths if os.path.isdir(p)]
            if not paths:
                messagebox.showinfo(APP_TITLE, "Choose your existing client folder(s) first.")
                return
        else:
            root_dir = os.path.expanduser(self.var_root.get().strip().strip('"'))
            paths = [root_dir]
            for on, target, name in (
                    (self.var_install_unez, self.var_unez_target, UNEZ_DIRNAME),
                    (self.var_install_fte, self.var_fte_target, FTE_DIRNAME)):
                if not on.get():
                    continue
                p = os.path.expanduser(target.get().strip().strip('"'))
                paths.append(os.path.normpath(p) if p else os.path.join(root_dir, name))
            paths = [p for p in paths if p and os.path.isdir(p)]
            if not paths:
                messagebox.showinfo(APP_TITLE, "Nothing installed yet:\n%s"
                                    % (root_dir or DEFAULT_ROOT))
                return
        for path in paths:
            if IS_WINDOWS:
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_TITLE, "An install is running. Cancel and quit?"):
                return
            self.cancel_event.set()
        self.root.destroy()


def main():
    _enable_dpi_awareness()
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
