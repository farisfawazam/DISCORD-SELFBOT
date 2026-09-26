@echo off
echo Menghentikan semua proses bot & server...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Discord Voice Multi-Bot*" >nul 2>&1
echo Selesai! Semua background bot dan web server telah dimatikan.
timeout /t 2 >nul
