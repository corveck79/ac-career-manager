@echo off
REM AC Career Manager - Build Standalone EXE
REM Requirements: Python 3.10+, PyInstaller installed

echo Building AC Career Manager...
echo.

REM Clean old builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist AC_Career_Manager.spec del AC_Career_Manager.spec

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Creating standalone EXE...
REM Build with PyInstaller
pyinstaller --onefile ^
    --windowed ^
    --name "AC_Career_Manager" ^
    --icon=icon.ico ^
    --add-data "templates:templates" ^
    --add-data "static:static" ^
    --add-data "config.json:." ^
    --add-data "career_manager.py:." ^
    --collect-all flask ^
    --collect-all flask_cors ^
    app.py

echo.
echo Build complete! EXE location: dist\AC_Career_Manager.exe
echo.
pause
