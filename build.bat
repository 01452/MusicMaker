@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python 3.12+ was not found on PATH.
    exit /b 1
)
if not exist "vendor\ffmpeg.exe" (
    echo Missing FFmpeg binary. Put ffmpeg.exe in vendor\ before building.
    exit /b 1
)
if not exist "resources\icons\musicmaker.ico" (
    echo Optional musicmaker.ico was not found; building without a Windows icon.
    py -m PyInstaller --noconfirm --clean --onefile --windowed --name MusicMaker --add-data "resources;resources" --add-data "vendor;vendor" main.py
) else (
    py -m PyInstaller --noconfirm --clean --onefile --windowed --icon "resources\icons\musicmaker.ico" --name MusicMaker --add-data "resources;resources" --add-data "vendor;vendor" main.py
)
if errorlevel 1 exit /b 1
echo Build complete: dist\MusicMaker.exe
endlocal
