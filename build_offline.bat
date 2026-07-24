@echo off
setlocal
cd /d "%~dp0"

if not exist wheelhouse (
  echo wheelhouse folder not found. Run prepare_offline_wheels.bat on an online Windows machine first.
  exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found.
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv || exit /b 1
)

.venv\Scripts\python -m pip install --no-index --find-links=wheelhouse -r requirements-build.txt || exit /b 1
.venv\Scripts\python -m unittest discover -s tests -v || exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean NumLockCalc.spec || exit /b 1

echo.
echo Offline build complete: dist\NumLockCalc.exe
endlocal
