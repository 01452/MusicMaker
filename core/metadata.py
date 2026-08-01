"""Safe media metadata inspection using Pillow and Mutagen."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from mutagen import File as MutagenFile, MutagenError


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageInfo:
    """Basic image details for the preview."""

    width: int
    height: int
    mode: str


@dataclass(frozen=True)
class AudioInfo:
    """Basic audio details for duration and display."""

    duration: float
    title: str


class MediaInspector:
    """Validate and inspect files without decoding their full contents."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}

    @classmethod
    def inspect_image(cls, path: str | Path) -> ImageInfo:
        """Return image dimensions or raise a user-friendly ValueError."""
        image_path = Path(path)
        if image_path.suffix.lower() not in cls.IMAGE_EXTENSIONS:
            raise ValueError("This image format is not supported. Use PNG, JPG, WEBP, or BMP.")
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                return ImageInfo(image.width, image.height, image.mode)
        except (OSError, UnidentifiedImageError) as error:
            LOGGER.info("Image inspection failed for %s: %s", image_path, error)
            raise ValueError("The selected image is corrupted or cannot be opened.") from error

    @classmethod
    def inspect_audio(cls, path: str | Path) -> AudioInfo:
        """Return audio duration from Mutagen or raise a friendly ValueError."""
        audio_path = Path(path)
        if audio_path.suffix.lower() not in cls.AUDIO_EXTENSIONS:
            raise ValueError("This audio format is not supported. Use MP3, WAV, FLAC, M4A, AAC, or OGG.")
        try:
            audio = MutagenFile(audio_path)
            duration = float(audio.info.length) if audio and audio.info else 0.0
            if duration <= 0:
                raise ValueError("Audio duration could not be determined.")
            title = audio_path.stem
            if audio and getattr(audio, "tags", None):
                tag_value = audio.tags.get("TIT2") or audio.tags.get("title")
                if tag_value:
                    title = str(tag_value[0] if isinstance(tag_value, list) else tag_value)
            return AudioInfo(duration, title)
        except (OSError, AttributeError, TypeError, ValueError, MutagenError) as error:
            LOGGER.info("Audio inspection failed for %s: %s", audio_path, error)
            if isinstance(error, ValueError):
                raise
            raise ValueError("The selected audio is corrupted or cannot be opened.") from error
