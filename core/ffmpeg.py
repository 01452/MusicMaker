"""FFmpeg discovery and command construction."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    """Raised when no usable FFmpeg executable is available."""


class FFmpegCommandError(RuntimeError):
    """Raised when the generated command cannot be assembled."""


@dataclass(frozen=True)
class VideoOptions:
    """Immutable encoding choices used to build one FFmpeg command."""

    width: int
    height: int
    fps: int
    codec: str
    bitrate: str
    ken_burns: bool
    fade_in: bool
    fade_out: bool
    auto_sharpen: bool
    film_grain: bool
    vignette: bool
    glow: bool
    movement: str


class FFmpegLocator:
    """Find bundled or PATH-provided FFmpeg binaries."""

    def __init__(self, application_directory: Path | None = None) -> None:
        self.application_directory = application_directory or Path(__file__).resolve().parent.parent

    def find(self) -> str:
        """Return an executable path, raising if FFmpeg is unavailable."""
        candidates = [
            self.application_directory / "ffmpeg" / "ffmpeg.exe",
            self.application_directory / "vendor" / "ffmpeg.exe",
            self.application_directory / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        path_value = shutil.which("ffmpeg")
        if path_value:
            return path_value
        raise FFmpegNotFoundError("FFmpeg is not installed or bundled with MusicMaker.")


class FFmpegCommandBuilder:
    """Build YouTube-compatible still-image video commands."""

    def build(
        self,
        ffmpeg: str,
        image: Path,
        audio: Path,
        output: Path,
        duration: float,
        options: VideoOptions,
    ) -> list[str]:
        """Create an FFmpeg command using only direct subprocess arguments."""
        if options.width <= 0 or options.height <= 0 or options.fps <= 0:
            raise FFmpegCommandError("Invalid video dimensions or frame rate.")
        video_codec = "libx265" if options.codec.upper() == "H265" else "libx264"
        filters: list[str] = []
        base = f"scale={options.width}:{options.height}:force_original_aspect_ratio=increase,crop={options.width}:{options.height}"
        if options.ken_burns:
            # The input image is oversized before zoompan so it can crop smoothly at every frame.
            zoom = "min(zoom+0.00035,1.18)"
            if options.movement == "Zoom Out":
                zoom = "if(eq(on,1),1.18,max(zoom-0.00035,1.0))"
            elif options.movement == "Pan Left":
                zoom = "1.08"
            elif options.movement == "Pan Right":
                zoom = "1.08"
            elif options.movement == "Random":
                zoom = "if(eq(on,1),1.0,min(zoom+0.00022,1.12))"
            pan_x = "(iw-iw/zoom)*0.50"
            pan_y = "(ih-ih/zoom)*0.50"
            if options.movement == "Pan Left":
                pan_x = "(iw-iw/zoom)*(1-on/(duration*fps))"
            elif options.movement == "Pan Right":
                pan_x = "(iw-iw/zoom)*(on/(duration*fps))"
            filters.append(
                f"scale={options.width * 2}:{options.height * 2}:force_original_aspect_ratio=increase,"
                f"crop={options.width * 2}:{options.height * 2},zoompan=z='{zoom}':x='{pan_x}':y='{pan_y}':d=1:s={options.width}x{options.height}:fps={options.fps}"
            )
        else:
            filters.append(base)
        if options.auto_sharpen:
            filters.append("unsharp=5:5:0.35:5:5:0")
        if options.film_grain:
            filters.append("noise=alls=4:allf=t+u")
        if options.vignette:
            filters.append("vignette=PI/5")
        if options.glow:
            filters.append("gblur=sigma=1,eq=brightness=0.02:saturation=1.04")
        if options.fade_in:
            filters.append("fade=t=in:st=0:d=0.8")
        if options.fade_out:
            fade_start = max(0.0, duration - 0.8)
            filters.append(f"fade=t=out:st={fade_start:.3f}:d=0.8")
        video_bitrate = [] if options.bitrate == "Auto" else ["-b:v", f"{options.bitrate}k"]
        return [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
            "-loop", "1", "-framerate", str(options.fps), "-i", str(image),
            "-i", str(audio), "-filter:v", ",".join(filters), "-t", f"{duration:.3f}",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", video_codec, "-preset", "medium",
            *video_bitrate, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(output),
        ]
