from qtpy.QtCore import QEvent, QSize
from qtpy.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame


class FittingLineEdit(QLineEdit):
    """A line edit that resizes itself to fit its current contents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_text_len = 0
        self.textChanged.connect(self._resize_to_contents)
        self._resize_to_contents()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._resize_to_contents()

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._resize_to_contents()
        return handled

    def _resize_to_contents(self) -> None:
        text = self.displayText() or self.placeholderText() or " "
        fm = self.fontMetrics()
        # boundingRect handles negative left bearings better than horizontalAdvance
        text_width = max(fm.horizontalAdvance(text), fm.boundingRect(text).width())

        option = QStyleOptionFrame()
        self.initStyleOption(option)
        cursor_width = self.style().pixelMetric(QStyle.PixelMetric.PM_TextCursorWidth, option, self)
        if cursor_width <= 0:
            cursor_width = 1
        # Keep a larger trailing buffer so QLineEdit does not start horizontal
        # scrolling while we are typing and resizing in the same frame.
        content_size = QSize(text_width + cursor_width + 16, fm.height())
        size = self.style().sizeFromContents(QStyle.ContentsType.CT_LineEdit, option, content_size, self)

        width = max(size.width(), self.minimumSizeHint().width())
        current_len = len(self.text())
        # While typing forward, avoid tiny shrink steps that cause horizontal text jitter.
        if self.hasFocus() and current_len >= self._last_text_len:
            width = max(width, self.width())
        self._last_text_len = current_len
        self.resize(width, size.height())
