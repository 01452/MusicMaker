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

    MOVEMENT_KEYS = ("Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Random")
    MOVEMENT_LABELS = ("Плавное приближение", "Плавное отдаление", "Панорама влево", "Панорама вправо", "Случайное движение")

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings_manager.load()
        self.worker: EncoderWorker | None = None
        self.started_at = 0.0
        self.audio_duration = 0.0
        self.image_info_text = "Изображение не выбрано"
        self._build_ui()
        self._load_settings()
        self._wire_signals()
        self._update_start_state()

    def _build_ui(self) -> None:
        self.setWindowTitle("MusicMaker — создание видео")
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
        subtitle = QLabel("Создайте видео из одного изображения и аудиотрека")
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
        preview_group = QGroupBox("ПРЕДПРОСМОТР")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = ImagePreview()
        preview_layout.addWidget(self.preview, 1)
        self.preview_info = QLabel("Изображение не выбрано")
        self.preview_info.setObjectName("muted")
        preview_layout.addWidget(self.preview_info)
        right.addWidget(preview_group, 1)
        self.output_group = self._make_output_group()
        right.addWidget(self.output_group)
        columns.addLayout(right, 2)
        root.addLayout(columns, 1)
        self.status_label = QLabel("Готово")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)
        self._create_menu()

    def _make_input_group(self) -> QGroupBox:
        group = QGroupBox("ВХОДНЫЕ ФАЙЛЫ")
        layout = QFormLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(11)
        self.audio_edit, audio_button = self._path_row("Аудиофайл", "Аудио (*.mp3 *.wav *.flac *.m4a *.aac *.ogg)")
        self.image_edit, image_button = self._path_row("Изображение", "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        self.output_edit, output_button = self._path_row("Папка вывода", "")
        layout.addRow("Аудиофайл", self._row_widget(self.audio_edit, audio_button))
        layout.addRow("Изображение", self._row_widget(self.image_edit, image_button))
        layout.addRow("Папка вывода", self._row_widget(self.output_edit, output_button))
        audio_button.clicked.connect(self._browse_audio)
        image_button.clicked.connect(self._browse_image)
        output_button.clicked.connect(self._browse_output)
        return group

    def _make_video_group(self) -> QGroupBox:
        group = QGroupBox("ВИДЕО")
        layout = QFormLayout(group)
        self.resolution = QComboBox(); self.resolution.addItems(["1920×1080", "2560×1440", "3840×2160"])
        self.fps = QComboBox(); self.fps.addItems(["24", "30", "60"])
        self.codec = QComboBox(); self.codec.addItems(["H264", "H265"])
        self.bitrate = QComboBox(); self.bitrate.addItem("Авто", "Auto"); self.bitrate.addItem("8000", "8000"); self.bitrate.addItem("12000", "12000"); self.bitrate.addItem("20000", "20000")
        layout.addRow("Разрешение", self.resolution)
        layout.addRow("Кадров/с", self.fps)
        layout.addRow("Кодек", self.codec)
        layout.addRow("Битрейт (кбит/с)", self.bitrate)
        return group

    def _make_effects_group(self) -> QGroupBox:
        group = QGroupBox("ЭФФЕКТЫ")
        layout = QVBoxLayout(group)
        self.ken_burns = QCheckBox("Кен Бёрнс")
        self.fade_in = QCheckBox("Появление")
        self.fade_out = QCheckBox("Исчезновение")
        self.auto_sharpen = QCheckBox("Авто-резкость")
        self.film_grain = QCheckBox("Зерно плёнки")
        self.vignette = QCheckBox("Виньетка")
        self.glow = QCheckBox("Свечение")
        effect_row = QHBoxLayout()
        for check in (self.ken_burns, self.fade_in, self.fade_out, self.auto_sharpen):
            effect_row.addWidget(check)
        layout.addLayout(effect_row)
        second_row = QHBoxLayout()
        for check in (self.film_grain, self.vignette, self.glow):
            second_row.addWidget(check)
        layout.addLayout(second_row)
        self.movement = QComboBox()
        for label, key in zip(self.MOVEMENT_LABELS, self.MOVEMENT_KEYS):
            self.movement.addItem(label, key)
        layout.addWidget(self.movement)
        return group

    def _make_output_group(self) -> QGroupBox:
        group = QGroupBox("ВЫВОД")
        layout = QVBoxLayout(group)
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("Моя песня.mp4")
        layout.addWidget(QLabel("Имя файла"))
        layout.addWidget(self.filename)
        self.start_button = QPushButton("СОЗДАТЬ ВИДЕО")
        self.start_button.setObjectName("startButton")
        self.start_button.setMinimumHeight(54)
        layout.addWidget(self.start_button)
        self.cancel_button = QPushButton("ОТМЕНИТЬ")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setVisible(False)
        layout.addWidget(self.cancel_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("0%")
        self.elapsed_label = QLabel("Прошло времени  —")
        self.remaining_label = QLabel("Осталось  —")
        self.speed_label = QLabel("Скорость кодирования  —")
        self.size_label = QLabel("Примерный размер  —")
        for label in (self.progress_label, self.elapsed_label, self.remaining_label, self.speed_label, self.size_label):
            label.setObjectName("muted")
            layout.addWidget(label)
        return group

    @staticmethod
    def _path_row(label: str, file_filter: str) -> tuple[QLineEdit, QPushButton]:
        edit = QLineEdit(); edit.setPlaceholderText(label)
        button = QPushButton("Обзор")
        button.setProperty("compact", True)
        return edit, button

    @staticmethod
    def _row_widget(edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget(); row = QHBoxLayout(widget); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(8)
        row.addWidget(edit, 1); row.addWidget(button)
        return widget

    def _create_menu(self) -> None:
        menu = self.menuBar().addMenu("Файл")
        paste_action = QAction("Вставить изображение из буфера", self)
        paste_action.triggered.connect(self.preview.paste_image)
        menu.addAction(paste_action)
        recent_menu = menu.addMenu("Недавние файлы")
        self.recent_menu = recent_menu
        self._refresh_recent_menu()
        help_menu = self.menuBar().addMenu("Помощь")
        about = QAction("О программе", self)
        about.triggered.connect(lambda: QMessageBox.about(self, "О программе", "MusicMaker\nБыстрое создание видео из изображения и аудио."))
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
        self.bitrate.setCurrentIndex(max(0, self.bitrate.findData(self.settings.bitrate)))
        for widget, value in ((self.ken_burns, self.settings.ken_burns), (self.fade_in, self.settings.fade_in), (self.fade_out, self.settings.fade_out), (self.auto_sharpen, self.settings.auto_sharpen), (self.film_grain, self.settings.film_grain), (self.vignette, self.settings.vignette), (self.glow, self.settings.glow)):
            widget.setChecked(value)
        movement_index = self.movement.findData(self.settings.movement)
        self.movement.setCurrentIndex(movement_index if movement_index >= 0 else 0)

    def _save_preferences(self) -> None:
        self.settings.audio_folder = str(Path(self.audio_edit.text()).parent) if self.audio_edit.text() else self.settings.audio_folder
        self.settings.image_folder = str(Path(self.image_edit.text()).parent) if self.image_edit.text() else self.settings.image_folder
        self.settings.output_folder = self.output_edit.text()
        self.settings.resolution = self.resolution.currentText().replace("×", "x")
        self.settings.fps = int(self.fps.currentText())
        self.settings.codec = self.codec.currentText()
        self.settings.bitrate = str(self.bitrate.currentData())
        self.settings.ken_burns = self.ken_burns.isChecked(); self.settings.fade_in = self.fade_in.isChecked(); self.settings.fade_out = self.fade_out.isChecked(); self.settings.auto_sharpen = self.auto_sharpen.isChecked()
        self.settings.film_grain = self.film_grain.isChecked(); self.settings.vignette = self.vignette.isChecked(); self.settings.glow = self.glow.isChecked(); self.settings.movement = str(self.movement.currentData())
        self.settings_manager.save(self.settings)
        self._update_preview_info()

    def _browse_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите аудиофайл", self.settings.audio_folder, "Аудио (*.mp3 *.wav *.flac *.m4a *.aac *.ogg)")
        if path: self.audio_edit.setText(path)

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", self.settings.image_folder, "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path: self._set_image(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите папку для видео", self.output_edit.text() or str(Path.home()))
        if path: self.output_edit.setText(path); self._save_preferences()

    def _set_image(self, path: str) -> None:
        try:
            info = MediaInspector.inspect_image(path)
        except ValueError as error:
            self._show_error(str(error)); return
        self.image_edit.setText(path)
        self.preview.set_image(path)
        self.image_info_text = f"Изображение {info.width} × {info.height}  •  {info.mode}"
        self._update_preview_info()
        self._update_start_state()

    def _audio_changed(self, path: str) -> None:
        if not path: self._update_start_state(); return
        try:
            info = MediaInspector.inspect_audio(path)
            self.audio_duration = info.duration
            self.filename.setText(self._default_filename(Path(path).stem))
            self.status_label.setText(f"Длительность аудио  {self._format_time(info.duration)}")
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
                self.image_info_text = f"Изображение {info.width} × {info.height}  •  {info.mode}"
                self._update_preview_info()
        self._update_start_state()

    def _update_preview_info(self) -> None:
        """Refresh preview metadata for the selected inputs and output format."""
        resolution = self.resolution.currentText()
        duration = self._format_time(self.audio_duration) if self.audio_duration else "—"
        self.preview_info.setText(f"{self.image_info_text}  •  Аудио {duration}  •  Вывод {resolution}")

    @staticmethod
    def _default_filename(stem: str) -> str:
        safe = "".join(char for char in stem if char not in '<>:/\\|?*"').strip() or "MusicMaker"
        return f"{safe}.mp4"

    def _update_start_state(self) -> None:
        """Enable creation once the form is filled; validate media on start."""
        missing: list[str] = []
        if not self.audio_edit.text().strip():
            missing.append("аудиофайл")
        if not self.image_edit.text().strip():
            missing.append("изображение")
        if not self.output_edit.text().strip():
            missing.append("папка вывода")
        ready = not missing and self.worker is None
        self.start_button.setEnabled(ready)
        self.start_button.setToolTip("Заполните: " + ", ".join(missing) if missing else "Создать видео")

    def _start_encoding(self) -> None:
        try:
            image = Path(self.image_edit.text()); audio = Path(self.audio_edit.text()); output_folder = Path(self.output_edit.text())
            MediaInspector.inspect_image(image); audio_info = MediaInspector.inspect_audio(audio)
            if not output_folder.exists(): output_folder.mkdir(parents=True, exist_ok=True)
            if not output_folder.is_dir(): raise ValueError("Указанный путь не является папкой.")
            filename = self.filename.text().strip() or self._default_filename(audio.stem)
            if not filename.lower().endswith(".mp4"): filename += ".mp4"
            output = output_folder / Path(filename).name
            width, height = (int(value) for value in self.resolution.currentText().split("×"))
            options = VideoOptions(width, height, int(self.fps.currentText()), self.codec.currentText(), str(self.bitrate.currentData()), self.ken_burns.isChecked(), self.fade_in.isChecked(), self.fade_out.isChecked(), self.auto_sharpen.isChecked(), self.film_grain.isChecked(), self.vignette.isChecked(), self.glow.isChecked(), str(self.movement.currentData()))
            ffmpeg = FFmpegLocator().find()
        except (ValueError, OSError) as error:
            self._show_error(str(error)); return
        except RuntimeError as error:
            self._show_error(str(error)); return
        self.settings.recent_files = [str(audio), str(image)] + [item for item in self.settings.recent_files if item not in {str(audio), str(image)}][:8]
        self._save_preferences(); self._refresh_recent_menu()
        self.worker = EncoderWorker(ffmpeg, image, audio, output, audio_info.duration, options)
        self.worker.progress.connect(self._on_progress); self.worker.completed.connect(self._on_completed); self.worker.failed.connect(self._on_failed); self.worker.cancelled.connect(self._on_cancelled)
        self.started_at = time.monotonic(); self.start_button.setVisible(False); self.cancel_button.setVisible(True); self.status_label.setText("Идёт создание видео…"); self._update_start_state(); self.worker.start()

    def _cancel_encoding(self) -> None:
        if self.worker: self.worker.cancel(); self.status_label.setText("Отмена…")

    def _on_progress(self, percent: int, elapsed: float, remaining: float, speed: float, seconds: int) -> None:
        self.progress_bar.setValue(percent); self.progress_label.setText(f"{percent}%"); self.elapsed_label.setText(f"Прошло времени  {self._format_time(elapsed)}"); self.remaining_label.setText(f"Осталось  {self._format_time(remaining) if remaining else '—'}"); self.speed_label.setText(f"Скорость кодирования  {speed:.2f}×")
        if self.audio_duration and speed: self.size_label.setText(f"Примерный размер  {self._estimate_size(speed):.1f} МБ")

    def _on_completed(self, path: str) -> None:
        self._finish_worker(); self.progress_bar.setValue(100); self.status_label.setText("Видео успешно создано")
        message = QMessageBox(self)
        message.setWindowTitle("Готово")
        message.setText(f"Видео создано:\n{path}")
        message.setIcon(QMessageBox.Icon.Information)
        open_button = message.addButton("Открыть видео", QMessageBox.ButtonRole.AcceptRole)
        folder_button = message.addButton("Открыть папку", QMessageBox.ButtonRole.ActionRole)
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() == open_button: os.startfile(path)  # type: ignore[attr-defined]
        elif message.clickedButton() == folder_button: self._open_folder(Path(path).parent)

    def _on_failed(self, message: str) -> None:
        self._finish_worker(); self._show_error(message)

    def _on_cancelled(self) -> None:
        self._finish_worker(); self.progress_bar.setValue(0); self.status_label.setText("Создание отменено")

    def _finish_worker(self) -> None:
        if self.worker:
            self.worker.deleteLater(); self.worker = None
        self.start_button.setVisible(True); self.cancel_button.setVisible(False); self._update_start_state()

    def _estimate_size(self, speed: float) -> float:
        bitrate = 8_000 if self.bitrate.currentData() == "Auto" else int(self.bitrate.currentData())
        return self.audio_duration * (bitrate + 192) / 8 / 1024

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"): return
        self.recent_menu.clear()
        for path in self.settings.recent_files:
            action = QAction(Path(path).name, self); action.setData(path); action.triggered.connect(lambda checked=False, value=path: self._load_recent(value)); self.recent_menu.addAction(action)
        if not self.settings.recent_files: self.recent_menu.addAction("Нет недавних файлов").setEnabled(False)

    def _load_recent(self, path: str) -> None:
        if Path(path).suffix.lower() in MediaInspector.IMAGE_EXTENSIONS: self._set_image(path)
        else: self.audio_edit.setText(path)

    def _open_folder(self, folder: Path) -> None:
        try: os.startfile(str(folder))  # type: ignore[attr-defined]
        except OSError as error: LOGGER.warning("Не удалось открыть папку: %s", error)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds)); return f"{total // 60:02d}:{total % 60:02d}"

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Ошибка", message)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._save_preferences()
        if self.worker:
            self.worker.cancel(); self.worker.wait(3000)
        event.accept()
