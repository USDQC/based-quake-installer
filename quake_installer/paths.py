"""Resource paths that work from source and from a PyInstaller build (onedir/onefile)."""

import os
import sys

IS_WINDOWS = os.name == "nt"


def app_base_dir():
    """Directory holding bundled data (tools/7za.exe).

    - PyInstaller onefile: the temp _MEIPASS extraction dir.
    - PyInstaller onedir (v6+): the _internal dir (also _MEIPASS).
    - From source: the project folder (parent of this package).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    return os.path.join(app_base_dir(), *parts)


def exe_side_path(*parts):
    """Path next to the running .exe (frozen) or project folder (source)."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), *parts)
    return os.path.join(app_base_dir(), *parts)
