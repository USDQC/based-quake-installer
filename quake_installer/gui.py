"""tkinter GUI (stdlib only). Install work runs in a background thread; the UI
is updated through a queue polled with Tk.after (Tk is not thread-safe).

This app is an installer only: progress + options. It installs engines and all
configured mods together. It does not launch games, write .bat helpers, or
create desktop shortcuts. FTE gets DISABLEHOMEDIR via default.fmf.
"""

import os
import queue
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, cfg, binds_mods, keycapture, mods as modlib, selfupdate, settings
from .constants import (APP_TITLE, DEFAULT_ROOT, LOOK_GL, LOOK_SOFT, MAX_NAME_LEN,
                        PLATFORM_LABELS, host_platform)
from .installer import Cancelled, InstallError, Options, Reporter, run_install
from .paths import IS_WINDOWS


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

    def __init__(self, parent, var, width=14, on_change=None):
        self.var = var
        self.on_change = on_change
        self.capturing = False
        self.enabled = True
        self.shown = tk.StringVar(value=var.get())
        var.trace_add("write", lambda *a: self._sync())
        self.entry = tk.Entry(parent, textvariable=self.shown, width=width,
                              state="readonly", cursor="hand2", relief="solid", bd=1,
                              readonlybackground="white", fg="black",
                              disabledbackground="#eeeeee", takefocus=0)
        self._ws = self.entry.tk.call("tk", "windowingsystem")
        e = self.entry
        e.bind("<ButtonPress>", self._on_button)
        e.bind("<KeyPress>", self._on_key)
        e.bind("<MouseWheel>", self._on_wheel)
        e.bind("<FocusOut>", lambda _e: self.cancel())
        self.btn = ttk.Button(parent, text="✕", width=2, command=self.clear, takefocus=0,
                              style="Clear.TButton")

    def grid(self, row, column, **kw):
        self.entry.grid(row=row, column=column, sticky="w", pady=1)
        self.btn.grid(row=row, column=column + 1, sticky="w", padx=(1, kw.get("gap", 14)),
                      pady=1)

    def _sync(self):
        if not self.capturing:
            self.shown.set(self.var.get())

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
        self.entry.configure(readonlybackground="#ffe680")
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
        self.entry.configure(readonlybackground="white")
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


class InstallerApp(object):
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()
        self.result = None
        self.last_opts = None
        self._step = (0, 6)

        root.title("%s  v%s" % (APP_TITLE, __version__))
        root.minsize(960, 680)
        try:
            ttk.Style().theme_use("vista" if IS_WINDOWS else "clam")
        except tk.TclError:
            pass
        ttk.Style().configure("Clear.TButton", padding=(2, 0))

        self.var_root = tk.StringVar(value=DEFAULT_ROOT)
        self.var_name = tk.StringVar(value="player")
        self.var_look = tk.StringVar(value=LOOK_SOFT)
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
        self._update_paths()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._poll)
        selfupdate.cleanup_old()  # the exe left over from the last self-update
        if self.var_self_auto.get():
            root.after(1500, lambda: self._start_self_check(quiet=True))

    # ------------------------------------------------------------------ layout
    def _build(self):
        pad = {"padx": 6, "pady": 3}
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(2, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        ttk.Label(
            outer, foreground="#555",
            text=("Installer — engines + all mods together. No launchers or .bat files. "
                  "FTE uses default.fmf (DISABLEHOMEDIR).")
        ).grid(row=0, column=0, columnspan=2, sticky="e")

        # Install path
        f = ttk.LabelFrame(outer, text="Install folder", padding=6)
        f.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        f.columnconfigure(0, weight=1)
        self.ent_root = ttk.Entry(f, textvariable=self.var_root)
        self.ent_root.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_browse = ttk.Button(f, text="Browse...", command=self._browse)
        self.btn_browse.grid(row=0, column=1)
        ttk.Label(f, textvariable=self.var_paths, foreground="#555").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

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

        bframe = ttk.LabelFrame(left, text="Binds (blank = unbound)", padding=6)
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
            preset_row, foreground="#555",
            text="QuakeWorld controls + weapons"
        ).pack(side="left", padx=(8, 0))
        ttk.Label(tab_qw, text=BIND_HELP).grid(row=2, column=0, columnspan=2, sticky="w",
                                                pady=(4, 0))

        canvas = tk.Canvas(tab_qw, highlightthickness=0, height=260)
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
        for i, (action_id, _cmd, label) in enumerate(cfg.BIND_ACTIONS):
            col = 0 if i < mid else 3
            row = i if i < mid else i - mid
            var = tk.StringVar(value="")
            self.bind_vars[action_id] = var
            ttk.Label(inner, text=label + ":", width=18, anchor="w").grid(
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
        ttk.Label(pick, foreground="#555",
                  text="saved to binds.cfg in the mod's folder; blank = skip").pack(side="left")
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
        m = ttk.LabelFrame(outer, text="Included mods (always installed with engines)", padding=6)
        m.grid(row=2, column=1, sticky="nsew", **pad)
        m.columnconfigure(0, weight=1)
        for r, spec in enumerate(self.mod_specs):
            ttk.Label(m, text=_mod_list_line(spec)).grid(
                row=r, column=0, sticky="w", pady=1)
        note_row = len(self.mod_specs)
        note = ttk.Label(
            m, foreground="#555", wraplength=280, justify="left",
            text="Installed with the engines. AirQuake, Quake Rally, and FvF are FTE-only."
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
        self.btn_folder = ttk.Button(b, text="Open folder", command=self._open_folder)
        self.btn_folder.pack(side="right")
        self.btn_self = ttk.Button(b, text="Update installer", command=self._start_self_check)
        self.btn_self.pack(side="right", padx=6)
        self.lbl_self = ttk.Label(b, textvariable=self.var_self, foreground="#1a4f8b")
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
        self.txt.tag_configure("err", foreground="#b00020")
        self.txt.tag_configure("ok", foreground="#1b5e20")
        self.txt.tag_configure("warn", foreground="#8a6d00")

    # ----------------------------------------------------------------- helpers
    def _scrollable(self, parent, height=200):
        """Canvas + scrollbar in parent; returns the inner frame (mouse wheel scrolls)."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = tk.Canvas(parent, highlightthickness=0, height=height)
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
        return {
            "root": self.var_root.get().strip(),
            "player_name": self.var_name.get(),
            "look": self.var_look.get(),
            "binds": {k: v.get() for k, v in self.bind_vars.items() if v.get().strip()},
            "mod_binds": {mk: {a: v.get() for a, v in mv.items() if v.get().strip()}
                          for mk, mv in self.mod_bind_vars.items()},
            "check_installer_updates": bool(self.var_self_auto.get()),
        }

    def _load_settings(self):
        """Last-used settings, or the Default preset on first run."""
        data = settings.load()
        if data and data.get("check_installer_updates") is False:
            self.var_self_auto.set(False)
        if not data:
            self._apply_preset("vanilla")
            self._log("First run: binds filled from the Default preset (stock default.cfg).")
            return
        if data.get("root"):
            self.var_root.set(data["root"])
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
        r = self.var_root.get().strip() or DEFAULT_ROOT
        self.var_paths.set("Creates:  %s   and   %s" % (
            os.path.join(r, "unezQuake"), os.path.join(r, "FTE")))

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
                    self.btn_cfg, self.btn_check, self.btn_self] +
                   self.radios + self.bind_entries + self.preset_buttons)
        for w in widgets:
            w.configure(state=st)
        for box in self.bind_boxes:
            box.set_enabled(not busy)
        self.btn_cancel.configure(state="normal" if busy else "disabled")

    # --------------------------------------------------------------- actions
    def _collect(self, configs_only, allow_empty_name=False):
        root = self.var_root.get().strip().strip('"')
        if not root:
            raise ValueError("Please choose an install folder.")
        if IS_WINDOWS and not (len(root) >= 3 and root[1] == ":" or root.startswith("\\\\")):
            raise ValueError("Please enter a full path, e.g. C:\\Games")
        root = os.path.expanduser(root)
        if not IS_WINDOWS and not os.path.isabs(root):
            raise ValueError("Please enter a full path, e.g. ~/Games")
        name = self.var_name.get()
        if not name.strip() and not allow_empty_name:
            raise ValueError("Please enter a player name.")
        name = name if name.strip() else "player"
        try:
            binds = self._collect_binds()
        except ValueError as exc:
            raise ValueError("Invalid key in binds: %s" % exc)
        # Always install every configured mod (no checkboxes).
        try:
            mod_binds = self._collect_mod_binds()
        except ValueError as exc:
            raise ValueError("Invalid key in mod binds: %s" % exc)
        return Options(root=root, player_name=name, look=self.var_look.get(),
                       binds=binds, write_bats=False, configs_only=configs_only,
                       mods=None, mod_files={}, mods_only=False, mod_binds=mod_binds,
                       platform=self.platform)

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
        note = updater.platform_mismatch_note(opts.root, opts.platform)
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
            items = updater.check_updates(opts.root, opts.platform, log=rep.log)
            self.q.put(("checked", items))
        except Exception as exc:
            self.q.put(("error", "Update check failed: %s" % exc))

    def _show_updates(self, items):
        self._set_busy(False)
        todo = [i for i in items if i.needs_update]
        for i in items:
            tag = "WARN: " if i.needs_update or i.status not in ("up to date",) else "OK  "
            self._log(tag + i.line())
        self.var_status.set("%d update(s) available." % len(todo) if todo
                            else "Everything is up to date.")
        win = tk.Toplevel(self.root)
        win.title("Check for updates")
        win.transient(self.root)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, font=("TkDefaultFont", 10, "bold"),
                  text=("Updates available:" if todo else "Everything is up to date.")
                  ).pack(anchor="w")
        tree = ttk.Treeview(frm, columns=("status", "detail"), height=min(14, len(items)))
        tree.heading("#0", text="Component")
        tree.heading("status", text="Status")
        tree.heading("detail", text="Details")
        tree.column("#0", width=260)
        tree.column("status", width=170)
        tree.column("detail", width=420)
        for i in items:
            tree.insert("", "end", text=i.title, values=(i.status, i.detail))
        tree.pack(fill="both", expand=True, pady=6)
        ttk.Label(frm, foreground="#555", wraplength=760, justify="left",
                  text="Update replaces engine files and mod paks only; your cfgs "
                       "(autoexec/binds/config.cfg, default.fmf) are kept.").pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        btn = ttk.Button(bar, text="Update %d" % len(todo) if todo else "Update",
                         state="normal" if todo else "disabled",
                         command=lambda: (win.destroy(), self._start_update(items)))
        btn.pack(side="right", padx=6)
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
        ttk.Label(frm, foreground="#555", wraplength=520, justify="left",
                  text="This updates the installer program only. Your games, mods and "
                       "configs are not touched.").pack(anchor="w", pady=(10, 0))
        ttk.Checkbutton(frm, text="Check for a new installer when it starts",
                        variable=self.var_self_auto,
                        command=self._save_self_auto).pack(anchor="w", pady=(6, 0))
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Later", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="Update now",
                   command=lambda: (win.destroy(), self._start_self_update(rel))
                   ).pack(side="right", padx=6)
        self.self_window = win

    def _save_self_auto(self):
        settings.update(check_installer_updates=bool(self.var_self_auto.get()))

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
                                      "install (engines + all mods)"))
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
        self._log("  UnezQuake : %s" % os.path.join(o.unez_dir, res.unez_exe or "?"))
        self._log("  FTE       : %s" % os.path.join(o.fte_dir, res.fte_exe or "?"))
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
        self._log("  FTE: run the exe from the FTE folder — default.fmf DISABLEHOMEDIR "
                  "replaces needing -nohome on the command line.")

    def _open_folder(self):
        path = self.var_root.get().strip()
        if not os.path.isdir(path):
            messagebox.showinfo(APP_TITLE, "Folder does not exist yet:\n%s" % path)
            return
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
