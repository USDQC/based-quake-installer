"""The Settings window (engines, folders, theme, installer updates)."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import existing as existing_mod, folders, manifest, settings
from .constants import APP_TITLE, DEFAULT_ROOT, FTE_DIRNAME, UNEZ_DIRNAME
from .paths import IS_WINDOWS

WRAP = 560


class SettingsDialog(object):
    """One Settings window for an InstallerApp. Save copies the values back."""

    def __init__(self, app):
        self.app = app
        self.win = win = tk.Toplevel(app.root)
        win.title("Settings")
        win.transient(app.root)
        win.bind("<Escape>", lambda _e: win.destroy())
        self.v_unez = tk.BooleanVar(value=app.var_install_unez.get())
        self.v_fte = tk.BooleanVar(value=app.var_install_fte.get())
        self.v_unez_path = tk.StringVar(value=app.var_unez_target.get())
        self.v_fte_path = tk.StringVar(value=app.var_fte_target.get())
        self.v_remember = tk.BooleanVar(value=app.var_remember_dirs.get())
        self.v_self = tk.BooleanVar(value=app.var_self_auto.get())
        self.v_theme = tk.StringVar(value=app.var_theme.get())
        self.hint_u = tk.StringVar()
        self.hint_f = tk.StringVar()

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)
        # CH - Settings content scrolls; Save/Cancel stay in a fixed footer so no
        # controls are clipped on small screens or at high DPI scaling.
        body = ttk.Frame(frm)
        body.grid(row=0, column=0, sticky="nsew")
        inner = app._scrollable(
            body, height=max(360, min(620, app.root.winfo_screenheight() - 260)))
        inner.columnconfigure(0, weight=1)
        self._build_engines(inner)
        self._build_folders(inner)
        self._build_appearance(inner)
        self._build_updates(inner)
        self._build_footer(frm)
        self._sync()
        from .gui import center_window
        center_window(win, app.root)

    # ------------------------------------------------------------- sections
    def _build_engines(self, inner):
        eng = ttk.LabelFrame(inner, text="Engines (full install)", padding=8)
        eng.grid(row=0, column=0, sticky="ew")
        eng.columnconfigure(1, weight=1)
        self.ent_u = ttk.Entry(eng, textvariable=self.v_unez_path)
        self.ent_f = ttk.Entry(eng, textvariable=self.v_fte_path)
        self.btn_u = ttk.Button(eng, text="Browse...",
                                command=lambda: self._browse(self.v_unez_path, "unez"))
        self.btn_f = ttk.Button(eng, text="Browse...",
                                command=lambda: self._browse(self.v_fte_path, "fte"))
        for row, (label, var, ent, btn, hint) in enumerate((
                ("unezQuake", self.v_unez, self.ent_u, self.btn_u, self.hint_u),
                ("FTE", self.v_fte, self.ent_f, self.btn_f, self.hint_f))):
            gap = 2 if row == 0 else 0
            ttk.Checkbutton(eng, text=label, variable=var, command=self._sync).grid(
                row=row * 2, column=0, sticky="w", pady=(0, gap))
            ent.grid(row=row * 2, column=1, sticky="ew", padx=6, pady=(0, gap))
            btn.grid(row=row * 2, column=2, pady=(0, gap))
            ttk.Label(eng, textvariable=hint, style="Muted.TLabel").grid(
                row=row * 2 + 1, column=1, columnspan=2, sticky="w", padx=6,
                pady=(0, 6 if row == 0 else 0))
            ent.bind("<KeyRelease>", lambda _e: self._hints())
        ttk.Label(eng, style="Muted.TLabel", wraplength=WRAP, justify="left",
                  text="To use the usual layout, leave these empty: unezQuake and FTE "
                       "each go in their own folder under your install folder. Or pick "
                       "a different folder for either one. The two clients must stay in "
                       "separate folders, not the install folder itself, and not inside "
                       "each other. An existing folder is reused and your cfg files are "
                       "never overwritten. Unticked engines are not downloaded, updated, "
                       "or given mods."
                  ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_folders(self, inner):
        fold = ttk.LabelFrame(inner, text="Folders", padding=8)
        fold.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(fold, text="Remember install directory and client folders",
                        variable=self.v_remember).pack(anchor="w")
        ttk.Label(fold, style="Muted.TLabel", wraplength=WRAP, justify="left",
                  text="When this is off, the install folder and client folders are not "
                       "remembered for next time. Your name, binds and look still are, "
                       "and Check for updates still uses the folders recorded from your "
                       "last install."
                  ).pack(anchor="w")

    def _build_appearance(self, inner):
        from .gui import THEMES
        look = ttk.LabelFrame(inner, text="Appearance", padding=8)
        look.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        row = ttk.Frame(look)
        row.pack(fill="x")
        ttk.Label(row, text="Theme:").pack(side="left")
        ttk.Combobox(row, textvariable=self.v_theme, state="readonly", width=10,
                     values=[label for _k, label in THEMES]).pack(side="left", padx=(6, 0))

    def _build_updates(self, inner):
        upd = ttk.LabelFrame(inner, text="Installer updates", padding=8)
        upd.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(upd, text="Check for a new installer when it starts",
                        variable=self.v_self).pack(anchor="w")
        ttk.Label(upd, style="Muted.TLabel", wraplength=WRAP, justify="left",
                  text="This only checks. A small notice appears, and nothing is "
                       "downloaded or replaced until you choose Update now."
                  ).pack(anchor="w")

    def _build_footer(self, frm):
        bar = ttk.Frame(frm)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bar, text="Save", command=self.save).pack(side="right")
        ttk.Button(bar, text="Cancel", command=self.win.destroy).pack(side="right", padx=6)

    # -------------------------------------------------------------- helpers
    def _browse(self, var, kind):
        d = filedialog.askdirectory(
            title="Choose the %s folder" % folders.NAMES[kind],
            initialdir=var.get() if os.path.isdir(var.get()) else None,
            mustexist=False, parent=self.win)
        if d:
            var.set(os.path.normpath(d))
            self._hints()

    def _root_dir(self):
        return folders.clean(self.app.var_root.get()) or DEFAULT_ROOT

    def _effective(self, var, name):
        p = folders.clean(var.get())
        return os.path.normpath(p) if p else os.path.join(self._root_dir(), name)

    def _hints(self):
        self.hint_u.set("-> " + self._effective(self.v_unez_path, UNEZ_DIRNAME))
        self.hint_f.set("-> " + self._effective(self.v_fte_path, FTE_DIRNAME))

    def _sync(self):
        for on, ent, btn in ((self.v_unez, self.ent_u, self.btn_u),
                             (self.v_fte, self.ent_f, self.btn_f)):
            state = "normal" if on.get() else "disabled"
            ent.configure(state=state)
            btn.configure(state=state)
        self._hints()

    @staticmethod
    def _norm(text):
        t = folders.clean(text)
        return os.path.normpath(t) if t else ""

    def _error(self, msg):
        messagebox.showerror(APP_TITLE, msg, parent=self.win)

    def validate(self):
        """(unez, fte) cleaned folder overrides, or None after showing an error."""
        u_on, f_on = self.v_unez.get(), self.v_fte.get()
        if not u_on and not f_on:
            self._error("Choose at least one engine.")
            return None
        u, f = self._norm(self.v_unez_path.get()), self._norm(self.v_fte_path.get())
        for label, p, example in (("unezQuake", u, "ezquake"), ("FTE", f, "FTE")):
            if p and not folders.is_full_path(p):
                self._error("Enter a full %s folder path, e.g. %s." % (
                    label, "C:\\Games\\" + example if IS_WINDOWS else "~/Games/" + example))
                return None
        root = self._root_dir()
        eu = self._effective(self.v_unez_path, UNEZ_DIRNAME) if u_on else None
        ef = self._effective(self.v_fte_path, FTE_DIRNAME) if f_on else None
        try:
            folders.check_engine_folders(
                root, eu, ef,
                installed=manifest.engine_folders(manifest.load(root), root))
        except folders.FolderError as exc:
            self._error(str(exc))
            return None
        for label, p, kind in (("unezQuake", u, "unez"), ("FTE", f, "fte")):
            if not p or not os.path.isdir(p):
                continue
            warn = (existing_mod.check_unez_folder(p) if kind == "unez"
                    else existing_mod.check_fte_folder(p))
            if warn and not messagebox.askyesno(
                    APP_TITLE, "This doesn't look like a %s folder:\n\n%s\n\n"
                    "Use it anyway?" % (label, "\n".join(warn)), parent=self.win):
                return None
        return u, f

    def save(self):
        checked = self.validate()
        if checked is None:
            return
        app = self.app
        u, f = checked
        app.var_install_unez.set(self.v_unez.get())
        app.var_install_fte.set(self.v_fte.get())
        app.var_unez_target.set(u)
        app.var_fte_target.set(f)
        app.var_remember_dirs.set(self.v_remember.get())
        app.var_self_auto.set(self.v_self.get())
        if self.v_theme.get() != app.var_theme.get():
            app.var_theme.set(self.v_theme.get())
            app._apply_theme(save=True)
        settings.save(app._settings_values())
        app._update_paths()
        self.win.destroy()
