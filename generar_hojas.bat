@echo off
rem Arrastrar un archivo .dxf sobre este archivo para generar las hojas de taller.
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if "%~1"=="" (
  echo Arrastre un archivo .dxf sobre generar_hojas.bat
  pause
  exit /b 1
)
set /p PROYECTO=Nombre del proyecto: 
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% generar_hojas.py "%~1" --proyecto "%PROYECTO%" --salida "%~dpn1_hojas"
echo.
echo Los archivos quedaron en la carpeta: %~dpn1_hojas
pause
