@echo off
rem ============================================================
rem  NotaINE - Activar inicio automatico con Windows
rem  Doble clic: NotaINE se abrira solo (minimizado) al prender
rem  la PC. Para cuando el operador lo necesite, el motor ya
rem  esta listo y procesa al instante.
rem ============================================================
cd /d "%~dp0"
if not exist "NotaINE.exe" (
    echo ERROR: este archivo debe estar en la misma carpeta que NotaINE.exe
    pause
    exit /b 1
)
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut([IO.Path]::Combine($ws.SpecialFolders('Startup'), 'NotaINE.lnk'));" ^
  "$lnk.TargetPath = [IO.Path]::Combine('%~dp0', 'NotaINE.exe');" ^
  "$lnk.Arguments = '--min';" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.Save()"
if %errorlevel%==0 (
    echo.
    echo LISTO: NotaINE se abrira automaticamente al prender la PC.
    echo Aparecera minimizado en la barra de tareas, calentando el motor.
    echo Al hacerle clic ya estara listo para procesar.
) else (
    echo ERROR al crear el acceso de inicio automatico.
)
echo.
pause
