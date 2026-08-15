# MusicMaker Agent Instructions

These instructions apply to the entire repository. Read them before changing code.

## Product

MusicMaker is a production-oriented Windows desktop application that converts one image and one audio file into a YouTube-compatible MP4 video.

The end user is non-technical. Preserve the one-click experience: the packaged application must run without a separate Python or FFmpeg installation.

All user-facing text, dialogs, statuses, tooltips, file-picker titles, and error messages must be in Russian. Source code, docstrings, comments, and commit messages may be in English.

## Allowed technology

- Python 3.12+
- PySide6
- FFmpeg invoked directly through `subprocess`
- Pillow
- Mutagen
- PyInstaller

Do not introduce MoviePy or another video-processing framework.

## Repository map

- `main.py`: application entry point and stylesheet loading
- `settings.py`: JSON-backed persistent settings
- `gui/main_window.py`: main view and UI controller
- `gui/preview.py`: image preview, clipboard paste, and drag-and-drop
- `core/metadata.py`: image/audio validation and metadata
- `core/ffmpeg.py`: FFmpeg discovery and command generation
- `core/encoder.py`: background process, cancellation, and progress parsing
- `resources/style.qss`: dark UI theme
- `build.bat`: PyInstaller one-file Windows build
- `release_windows.ps1`: local Windows release helper
- `.github/workflows/build-windows.yml`: Windows release workflow

Keep UI, metadata, command construction, process execution, and persistence responsibilities separated.

## Functional invariants

- The GUI must remain responsive while encoding. Never run FFmpeg on the UI thread.
- Audio must not receive fade or other effects.
- Video duration must match the audio duration. Keep `-shortest` and the explicit duration limit.
- Output must remain MP4 with H.264 or H.265 video, AAC audio, `yuv420p`, and `+faststart`.
- Preserve paths containing spaces, Cyrillic, and other Unicode characters. Pass subprocess arguments as a list; never build a shell command string.
- Validate media with Pillow and Mutagen before encoding and show friendly Russian errors.
- Cancellation must terminate FFmpeg and remove only the partial output created by the current job.
- Do not overwrite or delete unrelated user files.

## Ken Burns and effects

Ken Burns movement uses FFmpeg `zoompan` and must visibly move for the complete audio duration.

- Calculate `total_frames = ceil(duration * fps)`.
- Generate the complete motion sequence with `d=total_frames`.
- Base movement on the output-frame counter `on`.
- Do not change this back to `d=1`; that resets motion for repeated still-image input frames and makes the image appear stationary.
- Keep zoom and pan smooth, deterministic for explicit directions, and bounded to valid crop coordinates.
- `Random` may choose one supported movement once per encoding job.
- Fade filters apply to video only.

When modifying an effect, test it independently and together with every other effect. A command returning zero is insufficient: compare frames from the beginning, middle, and end to prove that the visual output changes.

## FFmpeg progress handling

FFmpeg `-progress pipe:1` values are not guaranteed to be numeric.

- Treat `N/A`, `NA`, `UNKNOWN`, empty values, and malformed values as unavailable.
- Never allow progress parsing to fail an otherwise successful encode.
- Determine final success from the FFmpeg exit code and existence of the expected output file.
- Keep elapsed time, remaining time, percentage, and speed updates safe when values are missing or zero.
- Log the generated command and FFmpeg error output, but do not expose confusing raw diagnostics as the primary user message.

## UI rules

- Keep the resizable dark Windows-oriented interface.
- Keep the large Russian `СОЗДАТЬ ВИДЕО` button.
- Enable the button when required fields are filled; perform authoritative file validation when the user starts encoding.
- Make selected effects unambiguous and show the active effect summary while encoding.
- Preserve drag-and-drop, clipboard paste, recent files, cancellation, open-video, and open-folder behavior.
- Do not fade audio.

## Settings compatibility

Settings are persisted as JSON under the user's local MusicMaker directory. Preserve backward compatibility with existing values such as `Auto`, `Zoom In`, `Zoom Out`, `Pan Left`, `Pan Right`, and `Random`. UI labels may be Russian, but stored internal identifiers should remain stable.

## Required verification

Before handing off a change, run at minimum:

```bash
python3 -m py_compile main.py settings.py core/*.py gui/*.py
```

For FFmpeg or effect changes:

1. Generate a short synthetic image and audio file.
2. Encode a baseline video without effects.
3. Encode each affected effect separately.
4. Encode all effects together.
5. Extract beginning, middle, and ending frames and compare them.
6. Inspect the output with `ffprobe` for duration, resolution, FPS, codecs, and pixel format.

Do not claim visual behavior is fixed based only on source inspection or command construction.

## Windows packaging

Production artifacts must be built on Windows; PyInstaller is not a cross-compiler.

The GitHub Actions workflow must:

- use Python 3.12 on `windows-latest`;
- download the approved static Windows FFmpeg binary;
- bundle `resources/` and `vendor/`;
- build with `--onefile` and `--windowed`;
- verify that `dist/MusicMaker.exe` exists and is plausibly sized;
- upload `MusicMaker-Windows-x64.zip` as an artifact;
- include the FFmpeg license when available.

After changing application code, a local syntax check does not replace a successful Windows workflow run.

## Code quality and repository hygiene

- Use type hints, classes, docstrings, logging, and PEP 8 formatting.
- Avoid mutable global application state.
- Prefer small focused methods over long one-line statements.
- Preserve unrelated working-tree changes.
- Do not commit generated executables, downloaded FFmpeg binaries, build directories, release artifacts, virtual environments, logs, `.DS_Store`, or `__pycache__`.
- Do not commit, push, change repository visibility, or create a release unless the user explicitly requests it.

