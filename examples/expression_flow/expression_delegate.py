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

        self._title_text = ""

    def setTitleText(self, text:str):
        self._title_text = text
        self.prepareGeometryChange()

    def titleText(self) -> str:
        return self._title_text

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

        painter.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self._title_text)

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
        x = 12 # Start with some padding to the left some room for the title
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

from qdagview3.views.utils.geo import makeArrowShape, makeVerticalRoundedPath

class LinkWidget(QGraphicsLineItem):
    def __init__(self, parent:QGraphicsItem|None=None):
        super().__init__(parent)
        palette = self.scene().palette() if self.scene() else QApplication.palette()
        self.setPen(QPen(palette.text(), 1.5))

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

from qdagview3.models.socket_based_nodes_model import GraphRole, GraphDataRole

class ExpressionGraphDelegate(AbstractGraphDelegate):
    @staticmethod
    def _normalize_role(index: QModelIndex) -> GraphRole:
        role = index.data(GraphDataRole)
        if role is not None:
            return role
        
        print(f"Warning: index {index} does not have a GraphDataRole set, defaulting to role based on index structure")
        if not index.parent().isValid():
            return GraphRole.Node
        elif index.parent().isValid() and not index.parent().parent().isValid():
            return GraphRole.Inlet # Default to inlet if role is not set TODO: enforce explicit setting?
        else:
            raise ValueError("Invalid index structure")
        
    def createRowWidget(self, parent_widget: ExpressionWidget|None, index:QModelIndex) -> ExpressionWidget|OutletWidget|InletWidget:
        match self._normalize_role(index):
            case GraphRole.Node:
                widget = ExpressionWidget(parent=parent_widget)
                widget.setTitleText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
                return widget
            
            case GraphRole.Inlet:
                inlet = InletWidget(parent=parent_widget)
                parent_widget.insertInlet(0, inlet)

                def port_position_changed(index=index):
                    self.portPositionChanged.emit(index)
                inlet.scene_position_changed.connect(port_position_changed)
                return inlet
            
            case GraphRole.Outlet:
                outlet = OutletWidget(parent=parent_widget)
                parent_widget.insertOutlet(0, outlet)

                def port_position_changed(index=index):
                    self.portPositionChanged.emit(index)
                outlet.scene_position_changed.connect(port_position_changed)
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
        
        line = QLineF(makeLineBetweenShapes(start_widget, end_widget, distance=10))
        if isinstance(start_widget, QGraphicsItem):
            p1 = start_widget.mapToScene(start_widget.boundingRect().center())
        else:
            p1 = start_widget
        if isinstance(end_widget, QGraphicsItem):
            p2 = end_widget.mapToScene(end_widget.boundingRect().center())
        else:
            p2 = end_widget
        line = QLineF(p1, p2)
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
    
    def setRowEditorData(self, row_widget:ExpressionWidget, index:QModelIndex):
        """Set the data for the row widget. This is called when a vertical header is updated of the nodes model."""
        ...
    def setRowModelData(self, row_widget:ExpressionWidget, index:QModelIndex):
        """Set the data for the vertical header. This is called when a row widget is edited."""
        ...

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
        
    def linkDirectionHint(self, start_index: QModelIndex, start_widget:RowWidget|None=None, event:QEvent|None=None) -> Literal['forward', 'backward', None]:
        # By default, do not provide any hint. Override this method to provide hints about the direction of the link being created.
        match self._normalize_role(start_index): # Just to enforce that the index is valid and has a role, since we are going to use the same logic in canStartLink and createLinkWidget, we want to make sure the role is valid as early as possible.
            case GraphRole.Node:
                return None # No hint for nodes, since they cannot be linked directly.
            case GraphRole.Inlet:
                return 'backward'
            case GraphRole.Outlet:
                return 'forward'
            case _:
                return None
            
    def canAcceptLink(self, start_index: QModelIndex, end_index: QModelIndex, start_widget:RowWidget|None=None, end_widget:RowWidget|None=None, event:QEvent|None=None) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (end_index.isValid() 
            and end_index.parent().isValid() # has parent
            and not end_index.parent().parent().isValid()):
            return True
        else:
            return False
