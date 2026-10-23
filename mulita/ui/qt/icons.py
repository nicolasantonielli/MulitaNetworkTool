from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtQuick import QQuickImageProvider
from PyQt5.QtSvg import QSvgRenderer

ICONS_DIR = Path(__file__).resolve().parent / 'icons'
TEMPLATE_COLOR = '#000000'
DEFAULT_SIZE = QSize(64, 64)


class IconProvider(QQuickImageProvider):
    """`image://icon/<nombre>/<rrggbb>`: los SVG se pintan con el color del tema."""

    def __init__(self, directory: Path = ICONS_DIR):
        super().__init__(QQuickImageProvider.Image)
        self._directory = directory
        self._sources: dict[str, str] = {}

    def requestImage(self, icon_id: str, requested_size: QSize):
        name, _, color = icon_id.partition('/')
        size = requested_size if requested_size.isValid() and not requested_size.isEmpty() else DEFAULT_SIZE

        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        source = self._source(name)
        if source:
            svg = source.replace(TEMPLATE_COLOR, f'#{color[-6:] or "ffffff"}')
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            QSvgRenderer(QByteArray(svg.encode())).render(painter)
            painter.end()
        return image, image.size()

    def _source(self, name: str) -> str:
        if name not in self._sources:
            path = self._directory / f'{name}.svg'
            self._sources[name] = path.read_text(encoding='utf-8-sig') if path.is_file() else ''
        return self._sources[name]
