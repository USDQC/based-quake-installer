"""UnezQuake + FTE Installer -- entry point.

Run on Windows:   python installer_gui.py
Build an exe:     build_exe.bat   (PyInstaller)
"""

import sys

if sys.version_info < (3, 8):
    sys.stderr.write("Python 3.8 or newer is required.\n")
    sys.exit(1)

from quake_installer.gui import main

if __name__ == "__main__":
    sys.exit(main())
