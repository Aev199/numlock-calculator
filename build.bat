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
.venv\Scripts\python generate_version_info.py || exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_build.ps1" -TargetPath "dist\NumCalc.exe" || exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean NumLockCalc.spec || exit /b 1
powershell -NoProfile -Command "$hash=(Get-FileHash -Algorithm SHA256 'dist\NumCalc.exe').Hash.ToLower(); Set-Content -Encoding ascii 'dist\NumCalc.exe.sha256.txt' ($hash + '  NumCalc.exe')" || exit /b 1

echo.
echo Build complete: dist\NumCalc.exe
echo SHA-256: dist\NumCalc.exe.sha256.txt
endlocal
