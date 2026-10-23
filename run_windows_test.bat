@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%run_windows_test.ps1"

if not exist "%PS1%" (
  echo No se encontro "%PS1%"
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" (
  echo.
  echo El script termino con error %ERR%.
)

endlocal & exit /b %ERR%
