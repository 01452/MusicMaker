# MusicMaker

MusicMaker is a native-feeling Windows desktop application that turns one image and one audio track into a YouTube-ready MP4. It uses PySide6 for the interface, Pillow and Mutagen for lightweight validation/metadata, and FFmpeg directly through `subprocess` for encoding. MoviePy is not used.

## Requirements

- Windows 10 or later
- Python 3.12+
- FFmpeg with H.264/H.265, AAC, and `yuv420p` support

Install Python dependencies:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

FFmpeg can be on `PATH` for source runs. For a packaged build, place `ffmpeg.exe` in `vendor\ffmpeg.exe`. The binary is intentionally not redistributed in this source project; obtain it from the official FFmpeg distribution appropriate for your organization.

Run from source:

```powershell
python main.py
```

## Build

Place `ffmpeg.exe` in `vendor\`, install PyInstaller, and run:

```powershell
python -m pip install pyinstaller
build.bat
```

The result is `dist\MusicMaker.exe`, built with `--onefile` and `--windowed`. The bundled FFmpeg executable is copied into the one-file application data bundle and discovered at runtime when present.

## Production Windows release

The repository includes `.github/workflows/build-windows.yml`. On GitHub, use **Actions → Build MusicMaker for Windows → Run workflow**. The workflow builds on a real Windows runner, downloads the static FFmpeg dependency, and publishes a `MusicMaker-Windows-x64.zip` artifact containing `MusicMaker.exe` and the README. The recipient extracts the ZIP and double-clicks `MusicMaker.exe`; Python and FFmpeg do not need to be installed separately.

If building locally on Windows, run `release_windows.ps1` from PowerShell. It performs the same dependency download, build, and ZIP creation. FFmpeg is downloaded from the Windows build source linked by the official FFmpeg download page; its license is included in the build input under `vendor\FFMPEG-LICENSE.txt` when supplied by the archive.

## Features

- PNG, JPG/JPEG, WEBP, BMP image support
- MP3, WAV, FLAC, M4A, AAC, and OGG audio support
- 1080p, 1440p, and 4K output at 24/30/60 FPS
- H.264/H.265 video with AAC audio and YUV420P pixel format
- Smooth FFmpeg `zoompan` Ken Burns motion: zoom in, zoom out, pan left, pan right, or random
- Image-only fade in/out; audio is not faded
- Sharpen, film grain, vignette, and glow filters
- Progress, elapsed time, remaining time, speed, and size estimate
- Drag/drop image selection, clipboard image paste, recent files, cancel, and output opening
- Preferences saved as JSON under `%LOCALAPPDATA%\MusicMaker\settings.json`

## Project layout

```text
MusicMaker/
├── main.py
├── settings.py
├── core/
│   ├── encoder.py
│   ├── ffmpeg.py
│   └── metadata.py
├── gui/
│   ├── main_window.py
│   └── preview.py
├── resources/icons/musicmaker.svg
├── build.bat
├── requirements.txt
└── README.md
```
