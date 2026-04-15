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

REM Use venv Python if available
echo  [2/3] Python omgeving controleren...
if not exist "venv\Scripts\python.exe" (
    echo  [!] venv niet gevonden, aanmaken met Python 3.12...
    py -3.12 -m venv venv
    venv\Scripts\pip install -r requirements.txt
    venv\Scripts\pip install pythonnet --pre --upgrade
)
set PYTHON=venv\Scripts\python.exe

echo  [3/3] App starten...
echo.
echo  Sluit dit venster of druk Ctrl+C om te stoppen.
echo.

REM Start Flask in background, then open Edge in app mode (native window look)
start "" /B %PYTHON% -c "import types,sys; sys.modules['webview']=types.ModuleType('webview'); from app import app; app.run(host='127.0.0.1',port=5000,debug=False,use_reloader=False)"

REM Wait for Flask to be ready
timeout /t 2 /nobreak >nul

REM Open Edge in app mode — looks like a native window
start "" "msedge.exe" --app=http://127.0.0.1:5000 --window-size=1280,900 --window-position=100,50

REM Keep window open so Flask keeps running
echo  Flask draait op http://127.0.0.1:5000
echo  Sluit dit venster om te stoppen.
echo.
pause
