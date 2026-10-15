@echo off
REM Lanzador de NotaINE (sin consola visible)
REM Doble click en este archivo para abrir la app.
cd /d "%~dp0"
start "" pythonw main.py
