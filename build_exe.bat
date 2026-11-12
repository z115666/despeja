@echo off
REM ==========================================================================
REM  Despeja - compila la aplicacion de escritorio para Windows (.exe)
REM  Doble clic en este archivo. Resultado: dist\Despeja\Despeja.exe
REM  Requisito: Python 3.12 de 64 bits (python.org, marcando "Add to PATH")
REM  Ciclo SDLC: pruebas + SAST (bandit) + auditoria de dependencias (pip-audit)
REM  antes de compilar; si algo falla, se detiene.
REM ==========================================================================
setlocal
cd /d "%~dp0"
title Despeja - compilando
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

REM --- Python (preferencia 3.12 > 3.11 > el que haya) ---
set "PY=py -3.12"
%PY% --version >nul 2>&1 || set "PY=py -3.11"
%PY% --version >nul 2>&1 || set "PY=py -3"
%PY% --version >nul 2>&1 || set "PY=python"
%PY% --version >nul 2>&1 || (
    echo [ERROR] No se encuentra Python. Instala Python 3.12 desde https://www.python.org
    pause & exit /b 1
)
echo Usando:
%PY% --version

REM --- Entorno virtual ---
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [1/7] Creando entorno virtual...
    %PY% -m venv .venv || goto :error
)
set "VPY=.venv\Scripts\python.exe"

echo.
echo [2/7] Instalando dependencias fijadas...
"%VPY%" -m pip install --upgrade pip >nul || goto :error
"%VPY%" -m pip install -r requirements-dev.txt || goto :error

echo.
echo [3/7] Pruebas unitarias...
if not exist "docs\informes" mkdir "docs\informes"
"%VPY%" -m pytest -q tests > "docs\informes\pytest.txt" 2>&1
if errorlevel 1 (
    type "docs\informes\pytest.txt"
    echo [ERROR] Hay pruebas que fallan. No se compila.
    pause & exit /b 1
)
echo   Pruebas: OK

echo.
echo [4/7] Analisis de seguridad del codigo ^(bandit^)...
"%VPY%" -m bandit -r despeja app.py -ll > "docs\informes\bandit.txt" 2>&1
if errorlevel 1 (
    type "docs\informes\bandit.txt"
    echo [ERROR] Bandit ha encontrado problemas de severidad media o alta. No se compila.
    pause & exit /b 1
)
echo   SAST: sin problemas de severidad media o alta

echo.
echo [5/7] Vulnerabilidades conocidas en dependencias ^(pip-audit^)...
"%VPY%" -m pip_audit -r requirements.txt > "docs\informes\pip-audit.txt" 2>&1
if errorlevel 1 (
    type "docs\informes\pip-audit.txt"
    echo.
    echo [AVISO] pip-audit ha encontrado vulnerabilidades o no ha podido consultar la base de datos ^(sin Internet^).
    choice /c SN /m "Compilar de todos modos"
    if errorlevel 2 exit /b 1
) else (
    echo   Dependencias: sin vulnerabilidades conocidas
)

REM --- WebView2 (motor de la ventana; viene con Windows 11) ---
set "WV2="
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2=1"
reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2=1"
if not defined WV2 (
    echo [AVISO] No se detecta Microsoft Edge WebView2 Runtime. La app lo necesita para abrir la ventana:
    echo         https://developer.microsoft.com/microsoft-edge/webview2/
)

echo.
echo [6/7] Empaquetando con PyInstaller...
taskkill /im Despeja.exe /f /t >nul 2>&1
set "DIST=dist"
set "WORK=build"
call :borrar_carpeta "dist\Despeja"
if exist "dist\Despeja" (
    echo [AVISO] La carpeta dist\Despeja esta bloqueada por otro programa; se usara otra carpeta.
    set "DIST=dist_%RANDOM%"
    set "WORK=build_%RANDOM%"
)
call :borrar_carpeta "build\Despeja"
REM La interfaz se copia archivo a archivo: demo.js (datos de prueba) NO va en el ejecutable
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --distpath "%DIST%" --workpath "%WORK%" ^
  --name Despeja ^
  --icon icono.ico ^
  --version-file version_info.txt ^
  --add-data "ui\index.html;ui" ^
  --add-data "ui\app.css;ui" ^
  --add-data "ui\app.js;ui" ^
  --add-data "ui\iconos.js;ui" ^
  --add-data "ui\fonts;ui\fonts" ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module PyQt5 ^
  --exclude-module PyQt6 ^
  --exclude-module PySide6 ^
  --exclude-module pytest ^
  app.py || goto :error

echo.
echo [7/7] Probando el .exe...
set "TEST=%TEMP%\despeja_test.txt"
if exist "%TEST%" del "%TEST%"
start /wait "" "%DIST%\Despeja\Despeja.exe" --autotest "%TEST%"
findstr /x /c:"OK" "%TEST%" >nul 2>&1 && goto :test_ok
echo.
echo [ERROR] El .exe se ha generado pero no arranca bien. Detalle:
if exist "%TEST%" (type "%TEST%") else (echo   no llego a ejecutarse)
echo Copia este mensaje y pasamelo.
pause
exit /b 1
:test_ok
echo   Autotest del .exe: OK

REM --- ZIP y hashes SHA-256 (integridad de la publicacion) ---
if exist "Despeja-Windows.zip" del "Despeja-Windows.zip"
%PS% -Command "Compress-Archive -Path '%DIST%\Despeja' -DestinationPath 'Despeja-Windows.zip'" || goto :error
%PS% -Command "Get-FileHash -Algorithm SHA256 '%DIST%\Despeja\Despeja.exe','Despeja-Windows.zip' | ForEach-Object { $_.Hash.ToLower() + '  ' + (Split-Path $_.Path -Leaf) } | Set-Content -Encoding ascii SHA256SUMS.txt" || goto :error

echo.
echo ==========================================================================
echo  LISTO
echo  App:        %CD%\%DIST%\Despeja\Despeja.exe
echo  Para pasar: %CD%\Despeja-Windows.zip
echo  Hashes:     %CD%\SHA256SUMS.txt
echo  Informes:   %CD%\docs\informes
echo  Consejo: para limpiar las partes de sistema, clic derecho en Despeja.exe ^>
echo           "Ejecutar como administrador" ^(o el boton dentro de la app^).
echo ==========================================================================
type SHA256SUMS.txt
start "" "%DIST%\Despeja"
pause
exit /b 0

:error
echo.
echo [ERROR] Algo ha fallado en el paso anterior. Revisa el mensaje de arriba.
pause
exit /b 1

:borrar_carpeta
if not exist "%~1" exit /b 0
for /l %%i in (1,1,6) do (
    rmdir /s /q "%~1" >nul 2>&1
    if not exist "%~1" exit /b 0
    ping -n 3 127.0.0.1 >nul
)
exit /b 1
