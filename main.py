"""Application entry point for MusicMaker."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from settings import SettingsManager


def configure_logging() -> None:
    """Configure a small rotating-free application log."""
    log_directory = Path.home() / "AppData" / "Local" / "MusicMaker"
    log_directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_directory / "musicmaker.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    """Start the Qt application and return its exit code."""
    configure_logging()
    application = QApplication(sys.argv)
    application.setApplicationName("MusicMaker")
    application.setOrganizationName("MusicMaker")
    style_path = Path(__file__).resolve().parent / "resources" / "style.qss"
    if style_path.exists():
        application.setStyleSheet(style_path.read_text(encoding="utf-8"))
    settings_manager = SettingsManager()
    window = MainWindow(settings_manager)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
