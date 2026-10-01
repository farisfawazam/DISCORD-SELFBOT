@echo off
echo Menghentikan bot discord...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *run.py*" >nul 2>&1
echo Selesai.
timeout /t 2 >nul
