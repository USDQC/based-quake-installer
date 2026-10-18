@echo off
rem Convenience launcher: runs the GUI from source with the installed Python.
cd /d "%~dp0"
where pyw >nul 2>&1 && (start "" pyw -3 installer_gui.py & exit /b)
where pythonw >nul 2>&1 && (start "" pythonw installer_gui.py & exit /b)
python installer_gui.py
