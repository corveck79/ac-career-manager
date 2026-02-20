@echo off
REM AC Career Manager - Build Standalone EXE

echo Building AC Career Manager...
echo.

REM Clean old builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist AC_Career_Manager.spec del AC_Career_Manager.spec

echo Creating standalone EXE...
call venv\Scripts\activate.bat

REM --onedir is required for PySide6/Qt: Qt needs helper processes as separate files
pyinstaller --onedir ^
    --windowed ^
    --name "AC_Career_Manager" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "config.json;." ^
    --collect-all flask ^
    --collect-all flask_cors ^
    app.py

echo.
if exist dist\AC_Career_Manager\AC_Career_Manager.exe (
    echo Build successful: dist\AC_Career_Manager\AC_Career_Manager.exe
) else (
    echo Build FAILED - check errors above
)
echo.
pause
