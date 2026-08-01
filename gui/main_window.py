"""Main MusicMaker window and interaction logic."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from core.encoder import EncoderWorker
from core.ffmpeg import FFmpegLocator, VideoOptions
from core.metadata import MediaInspector
from gui.preview import ImagePreview
from settings import AppSettings, SettingsManager


LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Modern, resizable MusicMaker application window."""

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings_manager.load()
        self.worker: EncoderWorker | None = None
        self.started_at = 0.0
        self.audio_duration = 0.0
        self.image_info_text = "No image selected"
        self._build_ui()
        self._load_settings()
        self._wire_signals()
        self._update_start_state()

    def _build_ui(self) -> None:
        self.setWindowTitle("MusicMaker")
        self.setMinimumSize(920, 700)
        self.resize(1080, 820)
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "musicmaker.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(30, 26, 30, 28)
        root.setSpacing(18)

        header = QHBoxLayout()
        brand = QLabel("MusicMaker")
        brand.setObjectName("brand")
        subtitle = QLabel("Turn one image and one song into a YouTube-ready video")
        subtitle.setObjectName("subtitle")
        header.addWidget(brand)
        header.addSpacing(14)
        header.addWidget(subtitle)
        header.addStretch()
        root.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(14)
        self.input_group = self._make_input_group()
        self.video_group = self._make_video_group()
        self.effects_group = self._make_effects_group()
        left.addWidget(self.input_group)
        left.addWidget(self.video_group)
        left.addWidget(self.effects_group)
        left.addStretch()
        columns.addLayout(left, 3)
        right = QVBoxLayout()
        right.setSpacing(14)
        preview_group = QGroupBox("PREVIEW")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = ImagePreview()
        preview_layout.addWidget(self.preview, 1)
        self.preview_info = QLabel("No image selected")
        self.preview_info.setObjectName("muted")
        preview_layout.addWidget(self.preview_info)
        right.addWidget(preview_group, 1)
        self.output_group = self._make_output_group()
        right.addWidget(self.output_group)
        columns.addLayout(right, 2)
        root.addLayout(columns, 1)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)
        self._create_menu()

    def _make_input_group(self) -> QGroupBox:
        group = QGroupBox("INPUT")
        layout = QFormLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(11)
        self.audio_edit, audio_button = self._path_row("Audio file", "Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg)")
        self.image_edit, image_button = self._path_row("Image file", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        self.output_edit, output_button = self._path_row("Output folder", "")
        layout.addRow("Audio file", self._row_widget(self.audio_edit, audio_button))
        layout.addRow("Image file", self._row_widget(self.image_edit, image_button))
        layout.addRow("Output folder", self._row_widget(self.output_edit, output_button))
        audio_button.clicked.connect(self._browse_audio)
        image_button.clicked.connect(self._browse_image)
        output_button.clicked.connect(self._browse_output)
        return group

    def _make_video_group(self) -> QGroupBox:
        group = QGroupBox("VIDEO")
        layout = QFormLayout(group)
        self.resolution = QComboBox(); self.resolution.addItems(["1920×1080", "2560×1440", "3840×2160"])
        self.fps = QComboBox(); self.fps.addItems(["24", "30", "60"])
        self.codec = QComboBox(); self.codec.addItems(["H264", "H265"])
        self.bitrate = QComboBox(); self.bitrate.addItems(["Auto", "8000", "12000", "20000"])
        layout.addRow("Resolution", self.resolution)
        layout.addRow("FPS", self.fps)
        layout.addRow("Codec", self.codec)
        layout.addRow("Bitrate (kbps)", self.bitrate)
        return group

    def _make_effects_group(self) -> QGroupBox:
        group = QGroupBox("EFFECTS")
        layout = QVBoxLayout(group)
        self.ken_burns = QCheckBox("Ken Burns")
        self.fade_in = QCheckBox("Fade In")
        self.fade_out = QCheckBox("Fade Out")
        self.auto_sharpen = QCheckBox("Auto sharpen")
        self.film_grain = QCheckBox("Film grain")
        self.vignette = QCheckBox("Vignette")
        self.glow = QCheckBox("Glow")
        effect_row = QHBoxLayout()
        for check in (self.ken_burns, self.fade_in, self.fade_out, self.auto_sharpen):
            effect_row.addWidget(check)
        layout.addLayout(effect_row)
        second_row = QHBoxLayout()
        for check in (self.film_grain, self.vignette, self.glow):
            second_row.addWidget(check)
        layout.addLayout(second_row)
        self.movement = QComboBox(); self.movement.addItems(["Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Random"])
        layout.addWidget(self.movement)
        return group

    def _make_output_group(self) -> QGroupBox:
        group = QGroupBox("OUTPUT")
        layout = QVBoxLayout(group)
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("My Song.mp4")
        layout.addWidget(QLabel("Filename"))
        layout.addWidget(self.filename)
        self.start_button = QPushButton("START")
        self.start_button.setObjectName("startButton")
        self.start_button.setMinimumHeight(54)
        layout.addWidget(self.start_button)
        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setVisible(False)
        layout.addWidget(self.cancel_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("0%")
        self.elapsed_label = QLabel("Elapsed  —")
        self.remaining_label = QLabel("Remaining  —")
        self.speed_label = QLabel("Encoding speed  —")
        self.size_label = QLabel("Estimated size  —")
        for label in (self.progress_label, self.elapsed_label, self.remaining_label, self.speed_label, self.size_label):
            label.setObjectName("muted")
            layout.addWidget(label)
        return group

    @staticmethod
    def _path_row(label: str, file_filter: str) -> tuple[QLineEdit, QPushButton]:
        edit = QLineEdit(); edit.setPlaceholderText(label)
        button = QPushButton("Browse")
        button.setProperty("compact", True)
        return edit, button

    @staticmethod
    def _row_widget(edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget(); row = QHBoxLayout(widget); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(8)
        row.addWidget(edit, 1); row.addWidget(button)
        return widget

    def _create_menu(self) -> None:
        menu = self.menuBar().addMenu("File")
        paste_action = QAction("Paste image from clipboard", self)
        paste_action.triggered.connect(self.preview.paste_image)
        menu.addAction(paste_action)
        recent_menu = menu.addMenu("Recent files")
        self.recent_menu = recent_menu
        self._refresh_recent_menu()
        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About MusicMaker", self)
        about.triggered.connect(lambda: QMessageBox.about(self, "MusicMaker", "MusicMaker\nFast image + audio video creation with FFmpeg."))
        help_menu.addAction(about)

    def _wire_signals(self) -> None:
        self.start_button.clicked.connect(self._start_encoding)
        self.cancel_button.clicked.connect(self._cancel_encoding)
        self.audio_edit.textChanged.connect(self._audio_changed)
        self.image_edit.textChanged.connect(self._image_changed)
        self.preview.image_dropped.connect(self._set_image)
        for widget in (self.resolution, self.fps, self.codec, self.bitrate, self.movement):
            widget.currentIndexChanged.connect(self._save_preferences)
        for widget in (self.ken_burns, self.fade_in, self.fade_out, self.auto_sharpen, self.film_grain, self.vignette, self.glow):
            widget.stateChanged.connect(self._save_preferences)

    def _load_settings(self) -> None:
        self.audio_edit.setText("")
        self.output_edit.setText(self.settings.output_folder)
        self.resolution.setCurrentText(self.settings.resolution.replace("x", "×"))
        self.fps.setCurrentText(str(self.settings.fps))
        self.codec.setCurrentText(self.settings.codec)
        self.bitrate.setCurrentText(self.settings.bitrate)
        for widget, value in ((self.ken_burns, self.settings.ken_burns), (self.fade_in, self.settings.fade_in), (self.fade_out, self.settings.fade_out), (self.auto_sharpen, self.settings.auto_sharpen), (self.film_grain, self.settings.film_grain), (self.vignette, self.settings.vignette), (self.glow, self.settings.glow)):
            widget.setChecked(value)
        self.movement.setCurrentText(self.settings.movement)

    def _save_preferences(self) -> None:
        self.settings.audio_folder = str(Path(self.audio_edit.text()).parent) if self.audio_edit.text() else self.settings.audio_folder
        self.settings.image_folder = str(Path(self.image_edit.text()).parent) if self.image_edit.text() else self.settings.image_folder
        self.settings.output_folder = self.output_edit.text()
        self.settings.resolution = self.resolution.currentText().replace("×", "x")
        self.settings.fps = int(self.fps.currentText())
        self.settings.codec = self.codec.currentText()
        self.settings.bitrate = self.bitrate.currentText()
        self.settings.ken_burns = self.ken_burns.isChecked(); self.settings.fade_in = self.fade_in.isChecked(); self.settings.fade_out = self.fade_out.isChecked(); self.settings.auto_sharpen = self.auto_sharpen.isChecked()
        self.settings.film_grain = self.film_grain.isChecked(); self.settings.vignette = self.vignette.isChecked(); self.settings.glow = self.glow.isChecked(); self.settings.movement = self.movement.currentText()
        self.settings_manager.save(self.settings)

    def _browse_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select audio", self.settings.audio_folder, "Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg)")
        if path: self.audio_edit.setText(path)

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select image", self.settings.image_folder, "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path: self._set_image(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder", self.output_edit.text() or str(Path.home()))
        if path: self.output_edit.setText(path); self._save_preferences()

    def _set_image(self, path: str) -> None:
        try:
            info = MediaInspector.inspect_image(path)
        except ValueError as error:
            self._show_error(str(error)); return
        self.image_edit.setText(path)
        self.preview.set_image(path)
        self.image_info_text = f"Image {info.width} × {info.height}  •  {info.mode}"
        self._update_preview_info()
        self._update_start_state()

    def _audio_changed(self, path: str) -> None:
        if not path: self._update_start_state(); return
        try:
            info = MediaInspector.inspect_audio(path)
            self.audio_duration = info.duration
            self.filename.setText(self._default_filename(Path(path).stem))
            self.status_label.setText(f"Audio duration  {self._format_time(info.duration)}")
            self._update_preview_info()
        except ValueError:
            self.audio_duration = 0.0
        self._update_start_state()

    def _image_changed(self, path: str) -> None:
        if path and Path(path).is_file():
            try:
                info = MediaInspector.inspect_image(path)
            except ValueError:
                pass
            else:
                self.preview.set_image(path)
                self.image_info_text = f"Image {info.width} × {info.height}  •  {info.mode}"
                self._update_preview_info()
        self._update_start_state()

    def _update_preview_info(self) -> None:
        """Refresh preview metadata for the selected inputs and output format."""
        resolution = self.resolution.currentText()
        duration = self._format_time(self.audio_duration) if self.audio_duration else "—"
        self.preview_info.setText(f"{self.image_info_text}  •  Audio {duration}  •  Output {resolution}")

    @staticmethod
    def _default_filename(stem: str) -> str:
        safe = "".join(char for char in stem if char not in '<>:/\\|?*"').strip() or "MusicMaker"
        return f"{safe}.mp4"

    def _update_start_state(self) -> None:
        ready = bool(self.audio_edit.text() and self.image_edit.text() and self.output_edit.text() and self.audio_duration > 0)
        self.start_button.setEnabled(ready and self.worker is None)

    def _start_encoding(self) -> None:
        try:
            image = Path(self.image_edit.text()); audio = Path(self.audio_edit.text()); output_folder = Path(self.output_edit.text())
            MediaInspector.inspect_image(image); audio_info = MediaInspector.inspect_audio(audio)
            if not output_folder.exists(): output_folder.mkdir(parents=True, exist_ok=True)
            if not output_folder.is_dir(): raise ValueError("The output path is not a folder.")
            filename = self.filename.text().strip() or self._default_filename(audio.stem)
            if not filename.lower().endswith(".mp4"): filename += ".mp4"
            output = output_folder / Path(filename).name
            width, height = (int(value) for value in self.resolution.currentText().split("×"))
            options = VideoOptions(width, height, int(self.fps.currentText()), self.codec.currentText(), self.bitrate.currentText(), self.ken_burns.isChecked(), self.fade_in.isChecked(), self.fade_out.isChecked(), self.auto_sharpen.isChecked(), self.film_grain.isChecked(), self.vignette.isChecked(), self.glow.isChecked(), self.movement.currentText())
            ffmpeg = FFmpegLocator().find()
        except (ValueError, OSError) as error:
            self._show_error(str(error)); return
        except RuntimeError as error:
            self._show_error(str(error)); return
        self.settings.recent_files = [str(audio), str(image)] + [item for item in self.settings.recent_files if item not in {str(audio), str(image)}][:8]
        self._save_preferences(); self._refresh_recent_menu()
        self.worker = EncoderWorker(ffmpeg, image, audio, output, audio_info.duration, options)
        self.worker.progress.connect(self._on_progress); self.worker.completed.connect(self._on_completed); self.worker.failed.connect(self._on_failed); self.worker.cancelled.connect(self._on_cancelled)
        self.started_at = time.monotonic(); self.start_button.setVisible(False); self.cancel_button.setVisible(True); self.status_label.setText("Encoding…"); self._update_start_state(); self.worker.start()

    def _cancel_encoding(self) -> None:
        if self.worker: self.worker.cancel(); self.status_label.setText("Cancelling…")

    def _on_progress(self, percent: int, elapsed: float, remaining: float, speed: float, seconds: int) -> None:
        self.progress_bar.setValue(percent); self.progress_label.setText(f"{percent}%"); self.elapsed_label.setText(f"Elapsed  {self._format_time(elapsed)}"); self.remaining_label.setText(f"Remaining  {self._format_time(remaining) if remaining else '—'}"); self.speed_label.setText(f"Encoding speed  {speed:.2f}×")
        if self.audio_duration and speed: self.size_label.setText(f"Estimated size  {self._estimate_size(speed):.1f} MB")

    def _on_completed(self, path: str) -> None:
        self._finish_worker(); self.progress_bar.setValue(100); self.status_label.setText("Video created successfully")
        message = QMessageBox(self)
        message.setWindowTitle("MusicMaker")
        message.setText(f"Finished encoding:\n{path}")
        message.setIcon(QMessageBox.Icon.Information)
        open_button = message.addButton("Open video", QMessageBox.ButtonRole.AcceptRole)
        folder_button = message.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() == open_button: os.startfile(path)  # type: ignore[attr-defined]
        elif message.clickedButton() == folder_button: self._open_folder(Path(path).parent)

    def _on_failed(self, message: str) -> None:
        self._finish_worker(); self._show_error(message)

    def _on_cancelled(self) -> None:
        self._finish_worker(); self.progress_bar.setValue(0); self.status_label.setText("Encoding cancelled")

    def _finish_worker(self) -> None:
        if self.worker:
            self.worker.deleteLater(); self.worker = None
        self.start_button.setVisible(True); self.cancel_button.setVisible(False); self._update_start_state()

    def _estimate_size(self, speed: float) -> float:
        bitrate = 8_000 if self.bitrate.currentText() == "Auto" else int(self.bitrate.currentText())
        return self.audio_duration * (bitrate + 192) / 8 / 1024

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"): return
        self.recent_menu.clear()
        for path in self.settings.recent_files:
            action = QAction(Path(path).name, self); action.setData(path); action.triggered.connect(lambda checked=False, value=path: self._load_recent(value)); self.recent_menu.addAction(action)
        if not self.settings.recent_files: self.recent_menu.addAction("No recent files").setEnabled(False)

    def _load_recent(self, path: str) -> None:
        if Path(path).suffix.lower() in MediaInspector.IMAGE_EXTENSIONS: self._set_image(path)
        else: self.audio_edit.setText(path)

    def _open_folder(self, folder: Path) -> None:
        try: os.startfile(str(folder))  # type: ignore[attr-defined]
        except OSError as error: LOGGER.warning("Could not open folder: %s", error)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds)); return f"{total // 60:02d}:{total % 60:02d}"

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "MusicMaker", message)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._save_preferences()
        if self.worker:
            self.worker.cancel(); self.worker.wait(3000)
        event.accept()
