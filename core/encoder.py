"""Background FFmpeg worker and progress parsing."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .ffmpeg import FFmpegCommandBuilder, VideoOptions


LOGGER = logging.getLogger(__name__)


class EncoderWorker(QThread):
    """Encode one video while emitting progress signals to the Qt UI."""

    progress = Signal(int, float, float, float, int)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, ffmpeg_path: str, image: Path, audio: Path, output: Path, duration: float, options: VideoOptions) -> None:
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.image = image
        self.audio = audio
        self.output = output
        self.duration = duration
        self.options = options
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = False

    def cancel(self) -> None:
        """Request cancellation and terminate FFmpeg if it is active."""
        self._cancel_requested = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        """Run FFmpeg and parse key/value progress output."""
        started = time.monotonic()
        command = FFmpegCommandBuilder().build(
            self.ffmpeg_path, self.image, self.audio, self.output, self.duration, self.options
        )
        LOGGER.info("Starting encode: %s", subprocess.list2cmdline(command))
        try:
            self._process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as error:
            self.failed.emit(f"Не удалось запустить FFmpeg: {error}")
            return
        current_seconds = 0.0
        speed = 0.0
        try:
            assert self._process.stdout is not None
            for line in self._process.stdout:
                if self._cancel_requested:
                    break
                key, _, value = line.strip().partition("=")
                if key == "out_time_ms":
                    parsed_seconds = self._parse_progress_seconds(value)
                    if parsed_seconds is not None:
                        current_seconds = max(0.0, parsed_seconds)
                elif key == "speed":
                    speed = self._parse_speed(value)
                if key in {"out_time_ms", "speed", "progress"}:
                    elapsed = time.monotonic() - started
                    percent = min(100, int(current_seconds / self.duration * 100)) if self.duration else 0
                    remaining = max(0.0, (self.duration - current_seconds) / speed) if speed > 0 else 0.0
                    self.progress.emit(percent, elapsed, remaining, speed, int(current_seconds))
            return_code = self._process.wait()
            stderr = self._process.stderr.read() if self._process.stderr else ""
            if self._cancel_requested:
                self._remove_partial_output()
                self.cancelled.emit()
            elif return_code != 0:
                LOGGER.error("FFmpeg failed (%s): %s", return_code, stderr.strip())
                self.failed.emit(self._friendly_error(stderr))
            elif not self.output.exists():
                self.failed.emit("FFmpeg завершил работу, но видео не было создано.")
            else:
                self.progress.emit(100, time.monotonic() - started, 0.0, speed, int(self.duration))
                self.completed.emit(str(self.output))
        except (OSError, ValueError) as error:
            LOGGER.exception("Unexpected encoder error")
            self.failed.emit(f"Ошибка создания видео: {error}")

    def _remove_partial_output(self) -> None:
        try:
            if self.output.exists():
                self.output.unlink()
        except OSError:
            LOGGER.warning("Could not remove partial output %s", self.output)

    @staticmethod
    def _parse_speed(value: str) -> float:
        try:
            return float(value.rstrip("x"))
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_progress_seconds(value: str) -> float | None:
        """Convert FFmpeg progress time to seconds, ignoring sentinel values."""
        if not value or value.upper() in {"N/A", "NA", "UNKNOWN"}:
            return None
        try:
            return float(value) / 1_000_000.0
        except ValueError:
            return None

    @staticmethod
    def _friendly_error(stderr: str) -> str:
        text = stderr.lower()
        if "permission denied" in text or "access is denied" in text:
            return "Windows запретил доступ к папке или файлу. Выберите другую папку."
        if "invalid data" in text or "decode" in text:
            return "FFmpeg не смог прочитать один из файлов. Возможно, файл повреждён."
        if "encoder" in text:
            return "Выбранный видеокодек недоступен в этой сборке FFmpeg."
        return "FFmpeg не смог создать видео. Проверьте входные файлы и папку вывода."
