@echo off
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo Membersihkan session lama...
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

python run.py
pause
