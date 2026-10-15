@echo off
rem  NotaINE - Quitar el inicio automatico con Windows
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$p = [IO.Path]::Combine($ws.SpecialFolders('Startup'), 'NotaINE.lnk');" ^
  "if (Test-Path $p) { Remove-Item $p; Write-Host 'LISTO: inicio automatico desactivado.' } else { Write-Host 'No estaba activado.' }"
echo.
pause
