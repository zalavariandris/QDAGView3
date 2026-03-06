from __future__ import annotations

from qtpy.QtCore import (
    Qt, QRectF, Signal, QLineF
)
from qtpy.QtGui import (
    QPainter,
    QPen,
    QPainterPath,
    QFontMetricsF
)
from qtpy.QtWidgets import (
    QGraphicsSceneHoverEvent, QStyle, QStyleOption,
    QApplication, 
    QGraphicsLineItem,
    QGraphicsItem, 
    QStyleOptionGraphicsItem, 
    QGraphicsObject,
    QWidget, QGraphicsTextItem
)


from qdagview3.views.utils.qt import distribute_items


class CellWidget(QGraphicsTextItem):
    def setPlainText(self, text: str) -> None:
        parent = self.parentItem()
        if isinstance(parent, ExpressionWidget):
            parent.prepareGeometryChange()

        super().setPlainText(text)

        if isinstance(parent, ExpressionWidget):
            parent.handleCellContentsChanged(self)

class ExpressionWidget(QGraphicsItem):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self._inlets = []
        self._outlets = []
        self._cells = []

        self._title_item = QGraphicsTextItem(self)
        self._title_item.setPlainText("-name-")
        self._title_item.setParentItem(self)
        self._position_title_item()

    def setTitleText(self, text:str):
        self._title_item.setPlainText(text)
        self._position_title_item()

    def titleText(self) -> str:
        return self._title_item.toPlainText()

    def _position_title_item(self):
        rect = self.boundingRect()
        title_rect = self._title_item.boundingRect()
        self._title_item.setPos(-title_rect.width(), rect.top())

    def boundingRect(self) -> QRectF:
        rect = QRectF(0, 0, 22, 22)
        
        for cell in self._cells:
            rect = rect.united(cell.mapRectToParent(cell.boundingRect()))

        # rect.adjust(-6, 2, 6, -2)
        return rect
    
    def paint(self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None, widget: QWidget | None = None) -> None:
        palette = self.scene().palette() if self.scene() else QApplication.palette()
        rect = self.boundingRect()

        pen = QPen(palette.text().color(), 0.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        if self.isSelected():
            painter.setBrush(palette.highlight())
        else:
            painter.setBrush(palette.base())

        rect = self.boundingRect()
        painter.drawRoundedRect(rect, 4, 4)

        # title_rect = self._title_rect().translated(0, rect.top())
        # painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title_text)

    def insertInlet(self, pos:int, inlet:InletWidget):
        inlet.setParentItem(self)
        self._inlets.insert(pos, inlet)
        self._arrange_inlets()

    def removeInlet(self, inlet:InletWidget):
        inlet.setParentItem(None)
        self._inlets.remove(inlet)
        self._arrange_inlets()

    def insertOutlet(self, pos:int, outlet:OutletWidget):
        outlet.setParentItem(self)
        self._outlets.insert(pos, outlet)
        self._arrange_outlets()

    def removeOutlet(self, outlet:OutletWidget):
        outlet.setParentItem(None)
        self._outlets.remove(outlet)
        self._arrange_outlets()

    def insertCell(self, pos:int, cell:CellWidget):
        self.prepareGeometryChange()
        cell.setParentItem(self)
        self._cells.insert(pos, cell)
        self._arrange_cells()

    def removeCell(self, cell:CellWidget):
        self.prepareGeometryChange()
        cell.setParentItem(None)
        self._cells.remove(cell)
        self._arrange_cells()

    def handleCellContentsChanged(self, cell: CellWidget):
        if cell not in self._cells:
            return

        self._arrange_cells()

    def _arrange_cells(self):
        self.prepareGeometryChange()
        x = 0
        for cell in self._cells:
            cell.setPos(x, 0)
            x += cell.boundingRect().width() + 2
        
        self._arrange_inlets()
        self._arrange_outlets()
        self.update()

    def _arrange_inlets(self):
        print(f"arranging inlets len({len(self._inlets)})")
        rect = self.boundingRect()
        
        for inlet in self._inlets:
            inlet.setPos(0, rect.top()-inlet.boundingRect().height())

        distribute_items(
            items = self._inlets, 
            rect = rect, 
            equal_spacing=False, 
            orientation=Qt.Orientation.Horizontal
        )

    def _arrange_outlets(self):
        rect = self.boundingRect()

        for outlet in self._outlets:
            outlet.setPos(0, rect.bottom())
        
        # todo: since we are aranging item inside a rect, 
        # consider aligning items inside it as well
        distribute_items(
            items = self._outlets, 
            rect = rect, 
            equal_spacing=False, 
            orientation=Qt.Orientation.Horizontal
        )


class InletWidget(QGraphicsObject, QGraphicsItem):
    scene_position_changed = Signal()
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

        self.name_text_item = QGraphicsTextItem(self)
        self.name_text_item.setPlainText("-inlet-")
        self.name_text_item.setPos(0, -22)
        self.name_text_item.setVisible(False)

        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        self.name_text_item.setVisible(True)
        self.update()
    
    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        self.name_text_item.setVisible(False)
        self.update()

    def setLabelText(self, text:str):
        self.name_text_item.setPlainText(text)
        fm = QFontMetricsF(self.name_text_item.font())
        text_width = fm.width(text)
        self.name_text_item.setPos(4, -fm.height()-4)

    def insertCell(self, pos:int, cell:CellWidget):
        cell.setParentItem(self)
        cell.setY(self.boundingRect().top()-cell.boundingRect().height())

    def removeCell(self, cell:CellWidget):
        cell.setParentItem(None)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, 8, 8)
    
    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        palette = self.scene().palette() if self.scene() else QApplication.palette()
        rect = self.boundingRect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(palette.highlight())
        else:
            painter.setBrush(palette.text())
        painter.drawEllipse(rect)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.scene_position_changed.emit()
        return super().itemChange(change, value)

class OutletWidget(InletWidget):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        self.name_text_item.setPlainText("-outlet-")
        self.name_text_item.setPos(0, 0)

    def setLabelText(self, text: str):
        super().setLabelText(text)
        fm = QFontMetricsF(self.name_text_item.font())
        text_width = fm.width(text)
        self.name_text_item.setPos(-text_width-4, self.boundingRect().bottom()-6)

from qdagview3.views.utils.geo import makeArrowShape, makeVerticalRoundedPath

class LinkWidget(QGraphicsLineItem):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        palette = self.scene().palette() if self.scene() else QApplication.palette()
        self.setPen(QPen(palette.text(), 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def setLine(self, line:QLineF):
        super().setLine(line)

    def boundingRect(self):
        _ = QRectF(self.line().p1(), self.line().p2())
        _ = _.normalized()
        r = 27
        _ = _.adjusted(-r,-r,r,r)
        return _
    
    def shape(self)->QPainterPath:
        path:QPainterPath = makeVerticalRoundedPath(self.line(), width=4)
        return path
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        palette = option.palette
        if self.isSelected():
            color = palette.accent().color()
        elif option.state & QStyle.StateFlag.State_MouseOver:
            color = palette.highlight().color()
        else:
            color = palette.text().color()

        painter.setPen(QPen(color, 2))
        arrow = makeVerticalRoundedPath(self.line(), 2)
        painter.drawPath(arrow)
