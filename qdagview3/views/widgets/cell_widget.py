from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

class CellWidget(QGraphicsWidget):
    _PADDING = (8, 2)

    def __init__(self, parent: QGraphicsItem|None=None):
        super().__init__(parent)
        self._text:str = ""
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _contentSize(self) -> QSizeF:
        fm = QFontMetrics(self.font())
        text_rect = fm.boundingRect(self._text)
        return QSizeF(
            float(text_rect.width() + self._PADDING[0] * 2),
            float(text_rect.height() + self._PADDING[1] * 2),
        )

    def setText(self, text:str):
        assert isinstance(text, str)
        if self._text == text:
            return
        self._text = text
        self.prepareGeometryChange()
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return f"{self._text}"

    def sizeHint(self, which: Qt.SizeHint, constraint: QSizeF = QSizeF()) -> QSizeF:
        size = self._contentSize()
        if which in (Qt.SizeHint.MinimumSize, Qt.SizeHint.PreferredSize, Qt.SizeHint.MaximumSize):
            return size
        return super().sizeHint(which, constraint)

    def boundingRect(self) -> QRectF:
        size = self._contentSize()
        return QRectF(0, 0, size.width(), size.height())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = ...) -> None:
        rect = self.boundingRect()
        scene = self.scene()
        if scene is None:
            return
        palette = scene.palette()
        painter.setPen(QPen(palette.text(), 1))
        painter.setBrush(palette.base())
        painter.drawRoundedRect(rect, 5, 5)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        super().paint(painter, option, widget)
