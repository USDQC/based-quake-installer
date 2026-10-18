# Manual screenshots. Run on an X display of at least 1600x1200 with a clean HOME and
# SHOT_INSTALL=<an up-to-date install root> (for the Check for updates window). Needs Pillow and scrot.
import os, sys, subprocess, tkinter as tk
from tkinter import ttk
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image
from quake_installer import gui, updater
import tempfile
OUT = os.path.join(HERE, "img") + os.sep
FULL = os.path.join(tempfile.gettempdir(), "_bqi_full.png")
root = tk.Tk(); root.geometry("+0+0")
app = gui.InstallerApp(root)
app.var_name.set("Ranger")
app.var_root.set("/home/player/Games")
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
outer_nb = [w for w in walk(root) if isinstance(w, ttk.Notebook)][0]
def grab(win, name):
    root.update(); win.update()
    subprocess.run(["scrot", "-o", FULL])
    x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
    Image.open(FULL).crop((x, y, x + w, y + h)).save(OUT + name)
def page(title):
    app.var_mod_page.set(title); app.mod_pages[title].tkraise()
def s0():
    app._log("Ready to install into /home/player/Games ...")
    grab(root, "main-window.png")
    outer_nb.select(1); page("Team Fortress")
    v = app.mod_bind_vars["fortress"]
    v["gren1"].set("g"); v["gren2"].set("f"); v["special"].set("MOUSE2"); v["reload"].set("r")
    root.after(700, s1)
def s1():
    grab(root, "mod-binds-tf.png"); page("Rune Quake"); root.after(700, s2)
def s2():
    grab(root, "mod-binds-rune.png")
    root_dir = os.environ["SHOT_INSTALL"]  # path of an existing, up-to-date install
    items = updater.check_updates(root_dir, app.platform, log=lambda *a: None)
    app._show_updates(items)
    root.after(1500, s3)
def s3():
    tops = [w for w in walk(root) if isinstance(w, tk.Toplevel)]
    grab(tops[-1], "update-check.png"); root.destroy()
root.after(2500, s0); root.mainloop()
