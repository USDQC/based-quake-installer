"""UnezQuake + FTE Installer -- entry point.

Run on Windows:   python installer_gui.py
Build an exe:     build_exe.bat   (PyInstaller -> dist\\BasedQuakeInstaller.exe)
Self-test:        installer_gui.py --self-test [report.json]
"""

import sys

if sys.version_info < (3, 8):
    sys.stderr.write("Python 3.8 or newer is required.\n")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        # Start-up check for CI / support: BasedQuakeInstaller.exe --self-test [report.json]
        from quake_installer import selftest
        sys.exit(selftest.run(gui=True, report=sys.argv[2] if len(sys.argv) > 2 else None))
    from quake_installer.gui import main
    sys.exit(main())
