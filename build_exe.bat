@echo off
rem Build the standalone Windows programs with PyInstaller (Windows 10/11 x64).
rem The GitHub Actions workflow .github/workflows/windows-exe.yml runs this same script.
rem
rem   build_exe.bat           -> dist\BasedQuakeInstaller.exe      (one file, windowed; what releases ship)
rem                              dist\BasedQuakeInstaller-cli.exe  (one file, console; same engine as installer_cli.py)
rem   build_exe.bat onedir    -> dist\BasedQuakeInstaller\BasedQuakeInstaller.exe (folder build)
rem
rem tools\7za.exe and its licence are bundled; at run time they're found through sys._MEIPASS.
rem Set BQI_PYTHON to pick the interpreter (default: "py -3" if present, else "python").
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
if defined BQI_PYTHON set "PY=%BQI_PYTHON%"

%PY% -c "import sys, tkinter; assert sys.version_info >= (3, 8); print('Python', sys.version.split()[0], 'Tk', tkinter.TkVersion)"
if errorlevel 1 (
  echo.
  echo ERROR: Python 3.8+ with tkinter is required. Install 64-bit Python from python.org
  echo        and keep "tcl/tk and IDLE" ticked in the installer.
  exit /b 1
)

if not exist "tools\7za.exe" (
  echo ERROR: tools\7za.exe missing - keep the tools folder next to this script.
  exit /b 1
)

%PY% -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 exit /b 1

set "MODE=--onefile"
if /i "%~1"=="onedir" set "MODE=--onedir"

set "COMMON=--noconfirm --clean --optimize 2 %MODE% --add-data tools\7za.exe;tools --add-data tools\7za-license.txt;tools --add-data quake_installer\vendor\sv_ttk;quake_installer\vendor\sv_ttk --add-data quake_installer\assets;quake_installer\assets --hidden-import quake_installer.gui --hidden-import quake_installer.selftest"
if exist "assets\icon.ico" set "COMMON=%COMMON% --icon assets\icon.ico"

%PY% -m PyInstaller %COMMON% --windowed --name BasedQuakeInstaller installer_gui.py
if errorlevel 1 (
  echo PyInstaller failed ^(GUI^).
  exit /b 1
)
if /i "%MODE%"=="--onefile" (
  %PY% -m PyInstaller %COMMON% --console --name BasedQuakeInstaller-cli installer_cli.py
  if errorlevel 1 (
    echo PyInstaller failed ^(CLI^).
    exit /b 1
  )
)

echo.
echo Build complete:
if /i "%MODE%"=="--onefile" (
  echo   dist\BasedQuakeInstaller.exe       ^(double-click; ship this^)
  echo   dist\BasedQuakeInstaller-cli.exe   ^(command line^)
) else (
  echo   dist\BasedQuakeInstaller\BasedQuakeInstaller.exe   ^(ship the whole folder^)
)
echo Check it with:  dist\BasedQuakeInstaller-cli.exe --self-test
endlocal
