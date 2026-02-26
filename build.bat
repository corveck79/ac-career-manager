@echo off
REM AC Career GT Edition - Build Standalone EXE

echo Building AC Career GT Edition...
echo.

REM Clean old builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist AC_Career_GT_Edition.spec del AC_Career_GT_Edition.spec

echo Creating standalone EXE...
call venv\Scripts\activate.bat

pyinstaller --onefile ^
    --windowed ^
    --name "AC_Career_GT_Edition" ^
    --icon "static\logo.ico" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "config.json;." ^
    --add-data "platform_paths.py;." ^
    --collect-all flask ^
    --collect-all flask_cors ^
    --collect-all webview ^
    app.py

echo.
if exist dist\AC_Career_GT_Edition.exe (
    echo Build successful: dist\AC_Career_GT_Edition.exe
) else (
    echo Build FAILED - check errors above
)
echo.
pause
