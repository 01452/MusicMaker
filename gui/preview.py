"""Image preview widget with clipboard and drag/drop support."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ImagePreview(QWidget):
    """Show a selected image and accept an image pasted from the clipboard."""

    image_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self._pixmap = QPixmap()
        self.label = QLabel("Перетащите изображение сюда\nили вставьте его из буфера обмена")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("previewLabel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_image(self, path: str) -> None:
        """Display an image from disk."""
        self._pixmap = QPixmap(path)
        self._refresh()

    def paste_image(self) -> None:
        """Save a clipboard image into the user's MusicMaker folder."""
        from PySide6.QtWidgets import QApplication

        image = QApplication.clipboard().image()
        if image.isNull():
            return
        target_directory = Path.home() / "AppData" / "Local" / "MusicMaker" / "clipboard"
        target_directory.mkdir(parents=True, exist_ok=True)
        target = target_directory / "clipboard-image.png"
        image.save(str(target), "PNG")
        self.image_dropped.emit(str(target))

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.image_dropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._refresh()
        super().resizeEvent(event)

    def _refresh(self) -> None:
        if self._pixmap.isNull():
            return
        self.label.setPixmap(self._pixmap.scaled(self.label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.label.setText("")
