@echo off
rem ============================================================
rem  NotaINE - Herramienta de diagnostico
rem  Doble clic: genera DIAGNOSTICO.txt junto a este archivo.
rem  Mandar ese archivo al administrador si el programa falla.
rem ============================================================
setlocal
cd /d "%~dp0"
set OUT=DIAGNOSTICO.txt

echo Generando diagnostico, espera unos segundos...

echo ============ DIAGNOSTICO NotaINE ============ > "%OUT%"
echo Fecha: %date% %time% >> "%OUT%"
echo Carpeta: %cd% >> "%OUT%"
echo. >> "%OUT%"

echo ---- Sistema ---- >> "%OUT%"
wmic cpu get name /value 2>nul | findstr "=" >> "%OUT%"
wmic computersystem get totalphysicalmemory /value 2>nul | findstr "=" >> "%OUT%"
wmic os get caption,version /value 2>nul | findstr "=" >> "%OUT%"
wmic logicaldisk where "DeviceID='C:'" get freespace /value 2>nul | findstr "=" >> "%OUT%"
echo. >> "%OUT%"

echo ---- Archivos del programa ---- >> "%OUT%"
if exist "NotaINE.exe" (echo NotaINE.exe: OK >> "%OUT%") else (echo NotaINE.exe: FALTA ^(se copio mal la carpeta^) >> "%OUT%")
if exist "_internal\" (echo carpeta _internal: OK >> "%OUT%") else (echo carpeta _internal: FALTA ^(copiar la carpeta COMPLETA^) >> "%OUT%")
if exist "_internal\models\PP-OCRv4_mobile_det\" (echo modelos OCR: OK >> "%OUT%") else (echo modelos OCR: FALTAN >> "%OUT%")
if exist "_internal\mpl-cache\" (echo cache de fuentes: OK ^(version nueva^) >> "%OUT%") else (echo cache de fuentes: NO ^(version vieja del programa - actualizar^) >> "%OUT%")
echo. >> "%OUT%"

echo ---- Ultimas lineas del log ---- >> "%OUT%"
if exist "notaine.log" (
    powershell -NoProfile -Command "Get-Content 'notaine.log' -Tail 40" >> "%OUT%" 2>nul
) else (
    echo No hay notaine.log ^(el programa no ha llegado a arrancar^) >> "%OUT%"
)
echo. >> "%OUT%"
echo ============ FIN ============ >> "%OUT%"

echo.
echo Listo. Se creo el archivo:
echo    %cd%\%OUT%
echo.
echo Mandale ese archivo al administrador (Alberto).
echo.
pause
