@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY set "PY=python"
"%PY%" -c "import pygame" 2>nul || "%PY%" -m pip install pygame-ce
"%PY%" zahon.py
if errorlevel 1 pause
