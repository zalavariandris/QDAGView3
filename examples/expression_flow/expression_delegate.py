from __future__ import annotations


from typing import Literal

from qtpy.QtCore import (
    Qt, QRectF, Signal, QLineF, QModelIndex, QPointF, QEvent, QPersistentModelIndex
)
from qtpy.QtGui import (
    QPainter,
    QPen,
    QPainterPath
)
from qtpy.QtWidgets import (
    QStyle, QStyleOption,
    QApplication, 
    QGraphicsLineItem,
    QGraphicsItem, 
    QStyleOptionGraphicsItem, 
    QGraphicsObject,
    QWidget, QGraphicsTextItem
)


from qdagview3.views.utils.geo import makeLineBetweenShapes


from qdagview3.views.utils.qt import distribute_items



from qdagview3.delegates.abstract_graph_delegate import AbstractGraphDelegate
from expression_widgets import ExpressionWidget, CellWidget, InletWidget, OutletWidget, LinkWidget

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
                persistent_index = QPersistentModelIndex(index)
                def port_position_changed(persistent_index=persistent_index):
                    index = QModelIndex(persistent_index)
                    self.portPositionChanged.emit(index)
                inlet.scene_position_changed.connect(port_position_changed)
                return inlet
            
            case GraphRole.Outlet:
                outlet = OutletWidget(parent=parent_widget)
                parent_widget.insertOutlet(0, outlet)
                persistent_index = QPersistentModelIndex(index)

                def port_position_changed(persistent_index=persistent_index):
                    index = QModelIndex(persistent_index)
                    self.portPositionChanged.emit(index)
                outlet.scene_position_changed.connect(port_position_changed)
                return outlet
            case _:
                raise ValueError("Invalid index structure")
                
    def destroyRowWidget(self, parent_widget: ExpressionWidget|None, widget: ExpressionWidget)->bool:
        if not isinstance(parent_widget, (ExpressionWidget, type(None))):
            raise TypeError("Parent widget must be an ExpressionWidget or None")
        
        match widget:
            case ExpressionWidget():
                widget.setParentItem(None)
                return True
            
            case InletWidget() | OutletWidget():
                widget.setParentItem(None)
                return True

            case _:
                raise TypeError("Widget must be an ExpressionWidget, InletWidget, or OutletWidget")
                return False

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

    def createLinkWidget(self, link_index: QModelIndex|None, source_widget:ExpressionWidget|None, target_widget:ExpressionWidget|None, ) -> LinkWidget:
        """Create a link widget. Links are added directly to the scene."""
        if not isinstance(source_widget, (QGraphicsItem, type(None))):
            raise TypeError("source_widget must be a QGraphicsItem or None")
        if not isinstance(target_widget, (QGraphicsItem, type(None))):
            raise TypeError("target_widget must be a QGraphicsItem or None")
        
        assert not (source_widget is None and target_widget is None), "At least one of source_widget or target_widget must be provided"
        
        scene = source_widget.scene() or target_widget.scene()
        assert scene is not None, "At least one of the widgets must be in a scene"
        if source_widget and target_widget:
            assert source_widget.scene() == target_widget.scene(), "source_widget and target_widget should be in the same scene"

        link_widget = LinkWidget()
        # scene.addItem(link_widget)  # Links are added to the scene, not to the inlet widget
        return link_widget
    
    def moveLinkWidget(self, link_widget: LinkWidget, start_widget: QGraphicsItem|QPointF, end_widget: QGraphicsItem|QPointF):
        if not isinstance(link_widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
        
        # print(f"Moving link widget between {start_widget} and {end_widget}")
        
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
    
    def destroyLinkWidget(self, link_widget: LinkWidget, source_widget:ExpressionWidget|None, target_widget:ExpressionWidget|None)->bool:
        if not isinstance(source_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"source_widget must be a QGraphicsItem or None, got {type(source_widget)} instead")
        if not isinstance(target_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"target_widget must be a QGraphicsItem or None, got {type(target_widget)} instead")
        if not isinstance(link_widget, LinkWidget):
            raise TypeError(f"Widget must be a LinkWidget, got {type(link_widget)} instead")
        
        link_widget.setParentItem(None)  # Remove from any parent item

        # Schedule widget for deletion to prevent memory leaks TODO:
        # widget.deleteLater()
        return True
    
    def setRowEditorData(self, row_widget:ExpressionWidget, index:QModelIndex):
        """Set the data for the row widget. This is called when a vertical header is updated of the nodes model."""
        row_widget.setTitleText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")

    def setRowModelData(self, row_widget:ExpressionWidget, index:QModelIndex):
        """Set the data for the vertical header. This is called when a row widget is edited."""
        ...

    def setCellEditorData(self, cell:CellWidget, index:QModelIndex):
        print(f"Setting cell editor data for index {index}, display role: {index.data(Qt.ItemDataRole.DisplayRole)}")
        cell.setPlainText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
    
    def setCellModelData(self, cell:CellWidget, index:QModelIndex):
        model = index.model()
        assert model is not None, "Index must have a model"
        model.setData(index, cell.toPlainText(), Qt.ItemDataRole.EditRole)

    def canStartLink(self, start_index: QModelIndex, start_widget:ExpressionWidget|None=None, event:QEvent|None=None) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (start_index.isValid() 
            and start_index.parent().isValid() # has parent
            and not start_index.parent().parent().isValid()):
            return True
        else:
            return False
        
    def linkDirectionHint(self, start_index: QModelIndex, start_widget:ExpressionWidget|None=None, event:QEvent|None=None) -> Literal['forward', 'backward', None]:
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
            
    def canAcceptLink(self, start_index: QModelIndex, end_index: QModelIndex, start_widget:ExpressionWidget|None=None, end_widget:ExpressionWidget|None=None, event:QEvent|None=None) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (end_index.isValid() 
            and end_index.parent().isValid() # has parent
            and not end_index.parent().parent().isValid()):
            return True
        else:
            return False
