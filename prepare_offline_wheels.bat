@echo off
setlocal
cd /d "%~dp0"

if not exist wheelhouse mkdir wheelhouse

py -3 -m pip download --only-binary=:all: --dest wheelhouse -r requirements-build.txt
if errorlevel 1 (
  echo.
  echo Не удалось скачать полный набор wheel-файлов.
  echo Запускайте этот скрипт на Windows с той же архитектурой и версией Python,
  echo что и на офлайн-машине.
  exit /b 1
)

echo.
echo Готово. Скопируйте весь проект вместе с папкой wheelhouse на офлайн-машину.
endlocal
