@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found.
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv || exit /b 1
)

.venv\Scripts\python -m pip install --upgrade pip || exit /b 1
.venv\Scripts\python -m pip install -r requirements-build.txt || exit /b 1
.venv\Scripts\python -m unittest discover -s tests -v || exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_build.ps1" -TargetPath "dist\NumLockCalc.exe" || exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean NumLockCalc.spec || exit /b 1

echo.
echo Build complete: dist\NumLockCalc.exe
endlocal
