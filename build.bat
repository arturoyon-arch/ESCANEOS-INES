@echo off
chcp 65001 > nul
echo.
echo ============================================
echo   NotaINE — Compilacion para produccion
echo ============================================
echo.

REM Verificar Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no encontrado en PATH.
    pause & exit /b 1
)

REM Instalar/actualizar PyInstaller
echo [1/3] Verificando PyInstaller...
python -m pip install pyinstaller --quiet --upgrade
if %errorlevel% neq 0 (
    echo ERROR al instalar PyInstaller.
    pause & exit /b 1
)

REM Limpiar builds anteriores
echo [2/3] Limpiando builds anteriores...
if exist dist\NotaINE rmdir /s /q dist\NotaINE
if exist build\NotaINE rmdir /s /q build\NotaINE

REM Compilar
echo [3/3] Compilando NotaINE.exe...
echo (Esto puede tardar varios minutos la primera vez)
echo.
pyinstaller NotaINE.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   ERROR en la compilacion.
    echo   Revisa los mensajes de arriba.
    echo ============================================
    pause & exit /b 1
)

echo.
echo ============================================
echo   Compilacion exitosa!
echo   Ejecutable en: dist\NotaINE\NotaINE.exe
echo ============================================
echo.

REM Copiar modelos OCR al directorio de distribución si existen
set MODELS_SRC=%USERPROFILE%\.paddlex\official_models
set MODELS_DST=dist\NotaINE\.paddlex\official_models
if exist "%MODELS_SRC%" (
    echo Copiando modelos OCR...
    xcopy /E /I /Q "%MODELS_SRC%" "%MODELS_DST%"
    echo Modelos copiados.
)

echo.
echo Listo. Puedes copiar la carpeta dist\NotaINE\ a cualquier PC.
pause
