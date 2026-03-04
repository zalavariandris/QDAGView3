from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *


from qdagview3.views.widgets.cell_widget import CellWidget


class RowWidget(QGraphicsWidget):
    scenePositionChanged = Signal(QPointF)

    def __init__(self, parent: QGraphicsItem|None=None):
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        layout.setContentsMargins(4,4,4,4)
        layout.setSpacing(2)
        self._header = QGraphicsWidget()
        self._header.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._header.setLayout(QGraphicsLinearLayout(Qt.Orientation.Horizontal))
        self._header.layout().setContentsMargins(0,0,0,0)
        self._header.layout().setSpacing(2)
        self._body = QGraphicsWidget()
        self._body.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._body.setLayout(QGraphicsLinearLayout(Qt.Orientation.Vertical))
        self._body.layout().setContentsMargins(0,0,0,0)
        self._body.layout().setSpacing(2)
        layout.addItem(self._header)
        layout.addItem(self._body)
        super().__init__(parent)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

        self.title_widget = CellWidget()
        self.title_widget.setText("Title")
        self._header.layout().addItem(self.title_widget)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                if self.scene():
                    # Emit signal when position changes
                    self.scenePositionChanged.emit(value)
                    
        return super().itemChange(change, value)

    def _refreshLayout(self) -> None:
        layout = self.layout()
        if isinstance(layout, QGraphicsLayout):
            layout.invalidate()
            layout.activate()
        self.prepareGeometryChange()
        self.updateGeometry()
        self.update()
        parent = self.parentItem()
        if isinstance(parent, QGraphicsWidget):
            parent.updateGeometry()

    def sizeHint(self, which: Qt.SizeHint, constraint: QSizeF = QSizeF()) -> QSizeF:
        layout = self.layout()
        if isinstance(layout, QGraphicsLayout):
            size = layout.effectiveSizeHint(which, constraint)
            if which in (Qt.SizeHint.MinimumSize, Qt.SizeHint.PreferredSize, Qt.SizeHint.MaximumSize):
                return size
        return super().sizeHint(which, constraint)

    def boundingRect(self) -> QRectF:
        size = self.sizeHint(Qt.SizeHint.PreferredSize)
        return QRectF(0, 0, size.width(), size.height())
    
    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = self.boundingRect()
        
        scene = self.scene()
        if scene is None:
            return
        palette = scene.palette()
        painter.setBrush(palette.alternateBase())
        if self.isSelected():
            painter.setBrush(palette.highlight())

        painter.drawRoundedRect(rect, 6, 6)

    def insertCell(self, pos:int, cell:CellWidget):
        assert isinstance(cell, CellWidget)
        header_layout = cast(QGraphicsLinearLayout, self._header.layout())
        header_layout.insertItem(pos, cell)
        self._refreshLayout()

    def removeCell(self, cell:CellWidget):
        assert isinstance(cell, CellWidget)
        header_layout = cast(QGraphicsLinearLayout, self._header.layout())
        header_layout.removeItem(cell)
        cell.setParentItem(None)
        self._refreshLayout()

    def insertChild(self, pos:int, child:Self):
        assert isinstance(child, RowWidget)
        body_layout = cast(QGraphicsLinearLayout, self._body.layout())
        body_layout.insertItem(pos, child)
        self._refreshLayout()

    def removeChild(self, child:Self):
        assert isinstance(child, RowWidget) 
        body_layout = cast(QGraphicsLinearLayout, self._body.layout())
        body_layout.removeItem(child)
        child.setParentItem(None)
        self._refreshLayout()

