"""Persistent user preferences and recent file handling."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


@dataclass
class AppSettings:
    """Settings stored between MusicMaker sessions."""

    audio_folder: str = ""
    image_folder: str = ""
    output_folder: str = ""
    resolution: str = "1920x1080"
    fps: int = 30
    codec: str = "H264"
    bitrate: str = "Auto"
    ken_burns: bool = True
    fade_in: bool = True
    fade_out: bool = True
    auto_sharpen: bool = True
    film_grain: bool = False
    vignette: bool = False
    glow: bool = False
    movement: str = "Zoom In"
    recent_files: list[str] = field(default_factory=list)


class SettingsManager:
    """Read and write preferences in the per-user application directory."""

    def __init__(self, path: Path | None = None) -> None:
        base = Path.home() / "AppData" / "Local" / "MusicMaker"
        self.path = path or base / "settings.json"

    def load(self) -> AppSettings:
        """Load settings, falling back to safe defaults on bad data."""
        if not self.path.exists():
            return AppSettings()
        try:
            values: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
            defaults = asdict(AppSettings())
            defaults.update({key: value for key, value in values.items() if key in defaults})
            return AppSettings(**defaults)
        except (OSError, TypeError, ValueError) as error:
            LOGGER.warning("Could not load settings: %s", error)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """Persist settings, creating the parent directory if necessary."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        except OSError as error:
            LOGGER.warning("Could not save settings: %s", error)

