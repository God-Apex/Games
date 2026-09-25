@echo off
rem Sestaví "APEX Kasino.exe" kompilátorem, který je součástí .NET Frameworku 4 ve Windows.
cd /d "%~dp0"
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /optimize+ /win32icon:src\apex.ico /out:"APEX Kasino.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll src\*.cs
if errorlevel 1 pause
