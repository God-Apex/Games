@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -c "import pygame" 2>nul || %PY% -m pip install pygame-ce
%PY% zahon.py
if errorlevel 1 pause
