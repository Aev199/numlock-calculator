@echo off
setlocal
cd /d "%~dp0"

if not exist wheelhouse (
  echo Папка wheelhouse не найдена.
  echo Сначала запустите prepare_offline_wheels.bat на Windows-машине с интернетом.
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

set PYTHON=.venv\Scripts\python.exe

%PYTHON% -m pip install --no-index --find-links=wheelhouse -r requirements-build.txt
if errorlevel 1 exit /b 1

%PYTHON% -m py_compile app.py
if errorlevel 1 exit /b 1

where node >nul 2>nul
if not errorlevel 1 (
  node tests\test_calc_core.js
  if errorlevel 1 exit /b 1
) else (
  echo Node.js не найден: JS-тесты пропущены, для сборки он не требуется.
)

%PYTHON% -m unittest discover -s tests -p "test_*.py"
if errorlevel 1 exit /b 1

%PYTHON% -m PyInstaller --noconfirm --clean NumLockCalc.spec
if errorlevel 1 exit /b 1

echo.
echo Готово: dist\NumLockCalc.exe
endlocal
