@echo off
chcp 65001 > nul

REM ── Si no estamos en ventana persistente, reabrirse con cmd /k ───────────
if not defined NOTAINE_INSTALANDO (
    set NOTAINE_INSTALANDO=1
    start "NotaINE - Instalador" cmd /k ""%~f0""
    exit /b
)

title NotaINE - Instalador
color 1F

echo.
echo  ================================================
echo    NotaINE - Instalacion en esta computadora
echo    Notaria Publica No. 134
echo  ================================================
echo.
echo  Carpeta de instalacion: %~dp0
echo.

REM ── Verificar que se ejecuta desde la carpeta extraida ───────────────────
if not exist "%~dp0main.py" (
    echo  ERROR: No encuentro los archivos de NotaINE.
    echo.
    echo  Asegurate de haber DESCOMPRIMIDO el ZIP antes
    echo  de ejecutar este instalador.
    echo.
    echo  Pasos:
    echo    1. Clic derecho en NotaINE_Instalador.zip
    echo    2. "Extraer todo..."
    echo    3. Dentro de la carpeta extraida, doble clic en INSTALAR.bat
    echo.
    pause
    exit /b 1
)

REM ── 1. Verificar Python ───────────────────────────────────────────────────
echo [1/4] Verificando Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Python no esta instalado. Intentando instalar automaticamente...
    echo  (Esto puede tardar unos minutos)
    echo.
    winget install --id Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo.
        echo  *** No se pudo instalar Python automaticamente. ***
        echo.
        echo  Instala Python manualmente:
        echo    1. Ve a: https://www.python.org/downloads/
        echo    2. Descarga Python 3.13 para Windows
        echo    3. Ejecuta el instalador y MARCA "Add Python to PATH"
        echo    4. Reinicia esta ventana y vuelve a ejecutar INSTALAR.bat
        echo.
        pause
        exit /b 1
    )
    echo  Python instalado. Reinicia esta ventana y ejecuta INSTALAR.bat de nuevo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% OK.
echo.

REM ── 2. Instalar dependencias ──────────────────────────────────────────────
echo [2/4] Instalando dependencias de Python...
echo  Esto puede tardar entre 5 y 15 minutos la primera vez.
echo  No cierres esta ventana.
echo.
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo  Advertencia: no se pudo actualizar pip, continuando...
)
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo  *** ERROR al instalar dependencias. ***
    echo  Verifica tu conexion a internet e intenta de nuevo.
    echo.
    pause
    exit /b 1
)
echo.
echo  Dependencias instaladas. OK.
echo.

REM ── 3. Descargar modelos OCR ──────────────────────────────────────────────
echo [3/4] Descargando modelos OCR (primera vez ~200 MB)...
echo  Esto solo ocurre una vez. Necesitas internet.
echo.
cd /d "%~dp0"
python -c "from core.ocr_engine import get_engine; get_engine(); print('Motor OCR listo.')"
echo.

REM ── 4. Crear acceso directo ───────────────────────────────────────────────
echo [4/4] Creando acceso directo en el Escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut([System.Environment]::GetFolderPath('Desktop') + '\NotaINE.lnk'); ^
   $py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; ^
   if (-not $py) { $py = 'pythonw.exe' }; ^
   $s.TargetPath = $py; ^
   $s.Arguments = '\"%~dp0main.py\"'; ^
   $s.WorkingDirectory = '%~dp0'; ^
   $s.IconLocation = '%~dp0LOGONUEVO.ico'; ^
   $s.Description = 'NotaINE - Extractor de datos INE Notaria 134'; ^
   $s.Save(); ^
   Write-Host 'Acceso directo creado en el Escritorio.'"
echo.

echo  ================================================
echo.
echo    Instalacion completada exitosamente!
echo.
echo    Haz doble clic en "NotaINE" del Escritorio
echo    para iniciar la aplicacion.
echo.
echo  ================================================
echo.
pause
