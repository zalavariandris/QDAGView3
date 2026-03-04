from __future__ import annotations


from typing import *
from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from qdagview3.views.widgets.link_widget import LinkWidgetStraight as LinkWidget
from qdagview3.views.utils.geo import makeLineBetweenShapes


from qdagview3.views.utils.qt import distribute_items

if TYPE_CHECKING:
    from qdagview3.views.graph_view import GraphView


from qdagview3.delegates.abstract_graph_delegate import AbstractGraphDelegate

class CellWidget(QGraphicsTextItem):
    ...

class ExpressionWidget(QGraphicsItem):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self._inlets = []
        self._outlets = []
        self._cells = []

    def boundingRect(self) -> QRectF:
        if not self._cells:
            return QRectF(0, 0, 60, 22)
        cell0 = self._cells[0]
        rect = cell0.mapRectToParent(cell0.boundingRect())
        for cell in self._cells[1:]:
            rect = rect.united(cell.mapRectToParent(cell.boundingRect()))

        rect.adjust(-6, 2,6,-2)
        return rect
    
    def paint(self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None, widget: QWidget | None = ...) -> None:
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
        cell.setParentItem(self)
        self._cells.insert(pos, cell)
        self._arrange_cells()

    def removeCell(self, cell:CellWidget):
        cell.setParentItem(None)
        self._cells.remove(cell)
        self._arrange_cells()

    def _arrange_cells(self):
        x = 0
        for cell in self._cells:
            x += cell.boundingRect().width() + 2
            cell.setPos(x, 0)
        self.prepareGeometryChange()

    def _arrange_inlets(self):
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

        for inlet in self._inlets:
            inlet.setPos(0, rect.bottom())
        
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
        painter.setPen(Qt.NoPen)
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
    def insertCell(self, pos:int, cell:CellWidget):
        super().insertCell(pos, cell)
        cell.setY(self.boundingRect().bottom())

class LinkWidget(QGraphicsLineItem):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        palette = self.scene().palette() if self.scene() else QApplication.palette()
        self.setPen(QPen(palette.text(), 1.5))

    def setLine(self, line:QLineF):
        super().setLine(line)

    def boundingRect(self) -> QRectF:
        return super().boundingRect()

class ExpressionGraphDelegate(AbstractGraphDelegate):
    def _get_kind(self, index: QModelIndex) -> Literal["expression", "inlet", "outlet"]:
        if not index.parent().isValid():
            return "expression"
        elif index.parent().isValid() and not index.parent().parent().isValid():
            return "inlet"
        else:
            raise ValueError("Invalid index structure")
        
    def createRowWidget(self, parent_widget: ExpressionWidget|None, index:QModelIndex) -> ExpressionWidget|OutletWidget|InletWidget:
        match self._get_kind(index):
            case "expression":
                return ExpressionWidget(parent=parent_widget)
            case "inlet":
                inlet = InletWidget(parent=parent_widget)
                parent_widget.insertInlet(0, inlet)

                def port_position_changed(index=index):
                    self.portPositionChanged.emit(index)
                inlet.scene_position_changed.connect(port_position_changed)
                return inlet
            case "outlet":
                outlet = OutletWidget(parent=parent_widget)
                parent_widget.insertOutlet(0, outlet)
                return outlet
            case _:
                raise ValueError("Invalid index structure")
                
    def destroyRowWidget(self, parent_widget: ExpressionWidget|None, widget: ExpressionWidget)->bool:
        if not isinstance(parent_widget, (QGraphicsScene, RowWidget)):
            raise TypeError("Parent widget must be a QGraphicsScene or QGraphicsItem")
        
        match widget:
            case ExpressionWidget():
                widget.setParentItem(None)
            
            case InletWidget() | OutletWidget():
                widget.setParentItem(None)

            case _:
                raise TypeError("Widget must be an ExpressionWidget, InletWidget, or OutletWidget")

    def createCellWidget(self, parent_widget: ExpressionWidget|InletWidget|OutletWidget, index: QModelIndex) -> CellWidget:
        match parent_widget:
            case ExpressionWidget():
                cell = CellWidget(index.data(Qt.ItemDataRole.DisplayRole), parent=parent_widget)
                parent_widget.insertCell(0, cell)
                return cell
        
            case InletWidget() | OutletWidget():
                cell = CellWidget(index.data(Qt.ItemDataRole.DisplayRole), parent=parent_widget)
                parent_widget.insertCell(0, cell)
                return cell
    
    def destroyCellWidget(self, parent_widget: ExpressionWidget|InletWidget|OutletWidget, widget: CellWidget)->bool:
        match parent_widget:
            case ExpressionWidget():
                parent_widget.removeCell(widget)
            
            case InletWidget() | OutletWidget():
                parent_widget.removeCell(widget)

            case _:
                raise TypeError("Parent widget must be an ExpressionWidget, InletWidget, or OutletWidget")
        
        return True

    def createLinkWidget(self, link_index: QModelIndex|None, source_widget:RowWidget|None, target_widget:RowWidget|None, ) -> LinkWidget:
        """Create a link widget. Links are added directly to the scene."""
        if not isinstance(source_widget, (QGraphicsItem, type(None))):
            raise TypeError("source_widget must be a QGraphicsItem or None")
        if not isinstance(target_widget, (QGraphicsItem, type(None))):
            raise TypeError("target_widget must be a QGraphicsItem or None")
        
        assert not (source_widget is None and target_widget is None), "At least one of source_widget or target_widget must be provided"
        
        scene = source_widget.scene() or target_widget.scene()
        assert scene is not None, "At least one of the widgets must be in a scene"
        if source_widget and target_widget:
            assert source_widget.scene() == target_widget.scene(), "source_widget and target_widget must be in the same scene"

        link_widget = LinkWidget()
        scene.addItem(link_widget)  # Links are added to the scene, not to the inlet widget
        return link_widget
    
    def moveLinkWidget(self, link_widget: LinkWidget, start_widget: QGraphicsItem|QPointF, end_widget: QGraphicsItem|QPointF):
        if not isinstance(link_widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
        
        print(f"Moving link widget between {start_widget} and {end_widget}")
        
        line = QLineF(makeLineBetweenShapes(start_widget, end_widget))
        link_widget.setLine(line)
    
    def destroyLinkWidget(self, link_widget: LinkWidget, source_widget:RowWidget|None, target_widget:RowWidget|None)->bool:
        if not isinstance(source_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"source_widget must be a QGraphicsItem or None, got {type(source_widget)} instead")
        if not isinstance(target_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"target_widget must be a QGraphicsItem or None, got {type(target_widget)} instead")
        if not isinstance(link_widget, LinkWidget):
            raise TypeError(f"Widget must be a LinkWidget, got {type(link_widget)} instead")
        
        link_widget.setParentItem(None)  # Remove from any parent item
        scene = source_widget.scene() if source_widget else target_widget.scene()
        if scene is not None:
            scene.removeItem(link_widget)
        # Schedule widget for deletion to prevent memory leaks TODO:
        # widget.deleteLater()
        return True

    def setCellEditorData(self, cell:CellWidget, index:QModelIndex):
        print(f"Setting cell editor data for index {index}, display role: {index.data(Qt.ItemDataRole.DisplayRole)}")
        cell.setPlainText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
    
    def setCellModelData(self, cell:CellWidget, index:QModelIndex):
        model = index.model()
        model.setData(index, cell._text, Qt.ItemDataRole.EditRole)

    def canStartLink(self, start_index: QModelIndex, start_widget:RowWidget|None=None, event:QEvent|None=None) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (start_index.isValid() 
            and start_index.parent().isValid() # has parent
            and not start_index.parent().parent().isValid()):
            return True
        else:
            return False
    
    def canAcceptLink(self, start_index: QModelIndex, end_index: QModelIndex, start_widget:RowWidget|None=None, end_widget:RowWidget|None=None, event:QEvent|None=None) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (end_index.isValid() 
            and end_index.parent().isValid() # has parent
            and not end_index.parent().parent().isValid()):
            return True
        else:
            return False
