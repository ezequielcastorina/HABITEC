@echo off
rem Crea dist\SIP_Paneles.exe (un solo archivo, sin consola, sin necesidad de Python para usarlo).
rem Hay que correrlo una vez en una PC con Windows que tenga Python instalado.
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SIP_Paneles ^
  --collect-submodules ezdxf --hidden-import crear_plantilla --hidden-import generar_ejemplo ^
  --hidden-import generar_hojas app_sip.py
if errorlevel 1 goto error
echo.
echo Listo: dist\SIP_Paneles.exe
echo Se puede copiar ese archivo a cualquier PC con Windows; no hace falta instalar Python.
pause
exit /b 0
:error
echo.
echo Hubo un error. Copie el mensaje de arriba y envielo para corregirlo.
pause
exit /b 1
