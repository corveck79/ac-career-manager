@echo off
title AC Career GT Edition
cd /d "%~dp0"

echo.
echo  ==========================================
echo    AC CAREER GT EDITION
echo  ==========================================
echo.

REM Stop any previously running Flask servers on port 5000
echo  [1/3] Stoppen van oude servers...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM Use venv Python if available, else create it
echo  [2/3] Python omgeving controleren...
if not exist "venv\Scripts\python.exe" (
    echo  [!] venv niet gevonden, aanmaken met Python 3.12...
    py -3.12 -m venv venv
    venv\Scripts\pip install -r requirements.txt
)
set PYTHON=venv\Scripts\python.exe

echo  [3/3] App starten...
echo.
echo  Sluit dit venster of druk Ctrl+C om te stoppen.
echo.

%PYTHON% app.py

pause
