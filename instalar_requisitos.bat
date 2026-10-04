@echo off
rem Ejecutar una sola vez (necesita Python instalado).
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -r requirements.txt
echo.
pause
