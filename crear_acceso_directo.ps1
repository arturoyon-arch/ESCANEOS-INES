# Crea un acceso directo de NotaINE en el Escritorio con el icono correcto.
# Ejecutar una sola vez despues de instalar.

$AppDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop "NotaINE.lnk"

$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($ShortcutPath)

$ExePath = Join-Path $AppDir "dist\NotaINE\NotaINE.exe"

if (Test-Path $ExePath) {
    $Shortcut.TargetPath       = $ExePath
    $Shortcut.WorkingDirectory = Join-Path $AppDir "dist\NotaINE"
} else {
    $Shortcut.TargetPath       = "pythonw.exe"
    $Shortcut.Arguments        = "`"$AppDir\main.py`""
    $Shortcut.WorkingDirectory = $AppDir
}

$Shortcut.IconLocation = Join-Path $AppDir "LOGONUEVO.ico"
$Shortcut.Description  = "NotaINE - Extractor de datos INE Notaria 134"
$Shortcut.Save()

Write-Host "Acceso directo creado: $ShortcutPath"
