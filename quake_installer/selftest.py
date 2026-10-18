"""--self-test: a quick start-up check, used by CI on the built (frozen) exe.

It touches nothing on disk except the optional report file. It checks:
- the package imports and reports its version,
- tkinter can open (and close) a hidden window (GUI only),
- on Windows, the bundled tools/7za.exe is found and runs,
- the built-in LH5 decoder imports,
- settings would go to %APPDATA% (Windows) / ~/.config (Linux), never next to the exe.
"""

import json
import os
import sys

from . import __version__
from .paths import IS_WINDOWS, app_base_dir, exe_side_path


def run(gui=False, report=None):
    res = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
           "meipass": getattr(sys, "_MEIPASS", None), "base_dir": app_base_dir(),
           "python": sys.version.split()[0], "checks": {}}
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            res["checks"][name] = {"ok": True, "detail": fn()}
        except Exception as exc:  # report every failure, don't stop at the first
            ok = False
            res["checks"][name] = {"ok": False, "detail": "%s: %s" % (type(exc).__name__, exc)}

    def tk_check():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return "Tk %s" % tk.TkVersion

    def sevenzip_check():
        from .extract import find_7za, run_7za
        path = find_7za()
        if not IS_WINDOWS:
            return "not Windows (7za on PATH: %s)" % path
        if not path:
            raise RuntimeError("bundled tools/7za.exe not found under %s" % app_base_dir())
        code, out = run_7za([], timeout=60)
        if "7-Zip" not in out:
            raise RuntimeError("7za exit %s, unexpected output %r" % (code, out[:200]))
        return "%s (%s)" % (path, out.strip().splitlines()[0])

    def lh5_check():
        from . import lha
        return lha.__name__

    def settings_check():
        from .settings import settings_dir
        d = os.path.abspath(settings_dir())
        exe_dir = os.path.abspath(exe_side_path())
        if res["frozen"] and os.path.normcase(d).startswith(os.path.normcase(exe_dir)):
            raise RuntimeError("settings dir %s is inside the exe folder %s" % (d, exe_dir))
        if IS_WINDOWS and os.environ.get("APPDATA") and not os.path.normcase(d).startswith(
                os.path.normcase(os.path.abspath(os.environ["APPDATA"]))):
            raise RuntimeError("settings dir %s is not under %%APPDATA%%" % d)
        return d

    def gui_import_check():
        from . import gui  # noqa: F401  (imports every module the window uses)
        return "ok"

    if gui:
        check("tkinter", tk_check)
    check("gui_import", gui_import_check)
    check("7za", sevenzip_check)
    check("lh5", lh5_check)
    check("settings_dir", settings_check)
    res["ok"] = ok
    text = json.dumps(res, indent=2)
    if report:
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if sys.stdout is not None:
        try:
            print(text)
        except Exception:
            pass
    return 0 if ok else 1
