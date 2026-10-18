@echo off
rem Build Based-Quake-Installer.exe with PyInstaller (run on Windows 10/11 x64).
rem   build_exe.bat           -> onedir build (recommended: fast start, fewer AV false positives)
rem   build_exe.bat onefile   -> single self-extracting .exe
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

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

%PY% -m pip install --upgrade -r requirements-build.txt
if errorlevel 1 exit /b 1

set "MODE=--onedir"
if /i "%~1"=="onefile" set "MODE=--onefile"

%PY% -m PyInstaller --noconfirm --clean --windowed %MODE% ^
  --name Based-Quake-Installer ^
  --add-data "tools;tools" ^
  installer_gui.py
if errorlevel 1 (
  echo PyInstaller failed.
  exit /b 1
)

rem Ship the optional mods drop-folder and example override next to the exe.
if /i "%MODE%"=="--onefile" (
  set "OUT=dist"
) else (
  set "OUT=dist\Based-Quake-Installer"
)
if not exist "%OUT%\mods" mkdir "%OUT%\mods"
copy /y "mods\README.txt" "%OUT%\mods\README.txt" >nul
copy /y "mods.example.json" "%OUT%\mods.example.json" >nul

echo.
echo Build complete:
if /i "%MODE%"=="--onefile" (
  echo   dist\Based-Quake-Installer.exe
) else (
  echo   dist\Based-Quake-Installer\Based-Quake-Installer.exe   ^(ship the whole folder^)
)
endlocal
