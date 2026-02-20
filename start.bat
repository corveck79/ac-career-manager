@echo off
title AC Career Manager
cd /d "%~dp0"

echo.
echo  ==========================================
echo    AC CAREER MANAGER
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
    echo  [!] venv niet gevonden, aanmaken...
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
)
set PYTHON=venv\Scripts\python.exe

echo  [3/3] Server starten op http://localhost:5000
echo.
echo  Browser opent automatisch over 2 seconden.
echo  Sluit dit venster of druk Ctrl+C om te stoppen.
echo.

REM Open browser after server has had time to start
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

%PYTHON% app.py

pause
