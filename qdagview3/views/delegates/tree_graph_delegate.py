from __future__ import annotations

import logging
import weakref

from PyQt6.QtCore import QRectF

logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *


from qdagview3.views.widgets.link_widget import LinkWidgetStraight as LinkWidget
from qdagview3.views.utils.geo import makeLineBetweenShapes

if TYPE_CHECKING:
    from qdagview3.views.graph_view import GraphView

from qdagview3.views.widgets.cell_widget import CellWidget
from qdagview3.views.widgets.row_widget import RowWidget


class TreeGraphDelegate(QObject):
    portPositionChanged = Signal(object)

    ## Root widgets
    def createRowWidget(self, parent_widget: QGraphicsScene|RowWidget, index:QModelIndex) -> RowWidget:
        if not isinstance(parent_widget, (QGraphicsScene, RowWidget)):
            raise TypeError("Parent widget must be a QGraphicsScene or QGraphicsItem")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        widget = RowWidget()
        def onScenePositionChanged(pos, idx=QPersistentModelIndex(index)):
            print(f"Scene position of port widget for index {idx} {idx.data(Qt.ItemDataRole.DisplayRole)} changed to {pos}")
            self.portPositionChanged.emit(QModelIndex(idx))
        widget.scenePositionChanged.connect(onScenePositionChanged)
        widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        match parent_widget:
            case QGraphicsScene():
                widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                
                widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                parent_widget.addItem(widget)


            case RowWidget():
                parent_widget.insertChildRow(index.column(), widget)

            case _:
                raise TypeError("Parent widget must be a QGraphicsScene or RowWidget")
        
        return widget

    def destroyRowWidget(self, parent_widget: QGraphicsScene, widget: RowWidget)->bool:
        if not isinstance(parent_widget, (QGraphicsScene, RowWidget)):
            raise TypeError("Parent widget must be a QGraphicsScene or QGraphicsItem")
        
        match parent_widget:
            case QGraphicsScene():
                parent_widget.removeItem(widget)
            case RowWidget():
                parent_widget.removeChildRow(widget)
                widget.deleteLater()
            case _:
                raise TypeError("Parent widget must be a QGraphicsScene or RowWidget")
        return True
    
    def createCellWidget(self, parent_widget: RowWidget, index: QModelIndex) -> CellWidget:
        if not isinstance(parent_widget, RowWidget):
            raise TypeError("Parent widget must be a RowWidget")

        cell = CellWidget()
        cell.setText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
        parent_widget.insertCell(index.column(), cell)
        return cell
    
    def destroyCellWidget(self, parent_widget: RowWidget, widget: CellWidget)->bool:
        if not isinstance(parent_widget, RowWidget):
            raise TypeError("Parent widget must be a RowWidget")
        if not isinstance(widget, CellWidget):
            raise TypeError("Widget must be a CellWidget")
        
        parent_widget.removeCell(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
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
        cell.setText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
    
    def setCellModelData(self, cell:CellWidget, index:QModelIndex):
        model = index.model()
        model.setData(index, cell._text, Qt.ItemDataRole.EditRole)

    def canStartLink(self, start_widget:RowWidget, start_index: QModelIndex, event:QMouseEvent) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (start_index.isValid() 
            and start_index.parent().isValid() # has parent
            and not start_index.parent().parent().isValid()):
            return True
        else:
            return False
    
    def canAcceptLink(self, start_widget:RowWidget, end_widget:RowWidget, start_index: QModelIndex, end_index: QModelIndex) -> bool:
        # By default, allow all links. Override this method to implement custom logic.
        if (end_index.isValid() 
            and end_index.parent().isValid() # has parent
            and not end_index.parent().parent().isValid()):
            return True
        else:
            return False
    # # Horizontal "Column" widgets
    # def createNodeColumnWidget(self, parent_widget: NodeWidget, ref: NodeRef, col:int, graphview:'GraphView'=None) -> CellWidget:
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     # if not index.isValid():
    #     #     raise ValueError("Index must be valid")

    #     cell = CellWidget()
    #     model = graphview._graph_model
    #     assert isinstance(model, AbstractGraphModel)
    #     header_data = model.nodeHeaderData(col, Qt.ItemDataRole.DisplayRole)
    #     data = model.nodeData(ref, col, Qt.ItemDataRole.DisplayRole)
    #     cell.setText(f"{header_data}: {data}")
    #     parent_widget.insertHeaderCell(col, cell)
    #     return cell
    
    # def destroyNodeColumnWidget(self, parent_widget: NodeWidget, widget: CellWidget):
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     if not isinstance(widget, CellWidget):
    #         raise TypeError("Widget must be a CellWidget")
        
    #     parent_widget.removeHeaderCell(widget)
    #     # Schedule widget for deletion - this automatically disconnects all signals
    #     widget.deleteLater()
    
    # # child widgets for the nodes
    # def createInletWidget(self, parent_widget: InletWidget, index: InletRef, graphview:'GraphView'=None) -> InletWidget:
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     # if not index.isValid():
    #     #     raise ValueError("Index must be valid")

    #     # get inlet position from graph controller TODO: this is a bit hacky, we should have a cleaner way to get the port position without relying on the graph controller
    #     graph_model = graphview._graph_model
    #     node_ref = graph_model.inletNode(index)
    #     inlets = graph_model.inlets(node_ref) # Ensure inlets are loaded for the node
    #     pos = inlets.index(index)
    #     if pos == -1:
    #         raise ValueError(f"Port {index} is not an inlet of node {node_ref}")
        
    #     widget = InletWidget()
    #     parent_widget.insertInlet(pos, widget)
        
    #     # Store the persistent index directly on the widget
    #     # This avoids closure issues entirely
    #     widget.setProperty("modelIndex", index)
        
    #     # Connect using a simple lambda that gets the property
    #     widget.scenePositionChanged.connect(
    #         lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
    #         # if widget.property("modelIndex").isValid() else None
    #     )
    #     return widget
    
    # def destroyInletWidget(self, parent_widget: NodeWidget, widget: InletWidget):
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     if not isinstance(widget, InletWidget):
    #         raise TypeError("Widget must be an InletWidget")
        
    #     parent_widget.removeInlet(widget)
    #     # Schedule widget for deletion - this automatically disconnects all signals
    #     widget.deleteLater()
    
    # def createOutletWidget(self, parent_widget: NodeWidget, index: QModelIndex, graphview:'GraphView'=None) -> OutletWidget:
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     # if not index.isValid():
    #     #     raise ValueError("Index must be valid")
        
    #     widget = OutletWidget()
    #     # get outlet position from graph controller TODO: this is a bit hacky, we should have a cleaner way to get the port position without relying on the graph controller
    #     graph_model = graphview._graph_model
    #     node_ref = graph_model.outletNode(index)
    #     outlets = graph_model.outlets(node_ref) # Ensure outlets are loaded for the node
    #     pos = outlets.index(index)
    #     if pos == -1:
    #         raise ValueError(f"Port {index} is not an outlet of node {node_ref}")

    #     parent_widget.insertOutlet(pos, widget)
        
    #     # Store the persistent index directly on the widget
    #     # This avoids closure issues entirely
    #     widget.setProperty("modelIndex", index)
        
    #     # Connect using a simple lambda that gets the property
    #     widget.scenePositionChanged.connect(
    #         lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
    #         # if widget.property("modelIndex").isValid() else None
    #     )
    #     return widget
    
    # def destroyOutletWidget(self, parent_widget: NodeWidget, widget: OutletWidget):
    #     if not isinstance(parent_widget, NodeWidget):
    #         raise TypeError("Parent widget must be a NodeWidget")
    #     if not isinstance(widget, OutletWidget):
    #         raise TypeError("Widget must be an OutletWidget")

    #     parent_widget.removeOutlet(widget)
    #     # Schedule widget for deletion - this automatically disconnects all signals
    #     widget.deleteLater()
        
    # def createAttributeWidget(self, parent_widget: NodeWidget|OutletWidget|InletWidget|LinkWidget, attribute: AttributeRef, graphview:'GraphView'=None) -> CellWidget:
    #     if not isinstance(parent_widget, (NodeWidget, OutletWidget, InletWidget, LinkWidget)):
    #         raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
    #     # if not index.isValid():
    #     #     raise ValueError("Index must be valid")

    #     match parent_widget:
    #         case NodeWidget():
    #             cell = CellWidget()
    #             owner = graphview._graph_model.attributeOwner(attribute)
    #             attributes = graphview._graph_model.attributes(owner)
    #             pos = attributes.index(attribute)
    #             if pos == -1:
    #                 raise ValueError(f"Attribute {attribute} is not an attribute of {owner}")
    #             parent_widget.insertSideCell(pos, cell)
    #             return cell
            
    #         case OutletWidget() | InletWidget() | LinkWidget():
    #             cell = CellWidget()
    #             owner = graphview._graph_model.attributeOwner(attribute)
    #             attributes = graphview._graph_model.attributes(owner)
    #             pos = attributes.index(attribute)
    #             if pos == -1:
    #                 raise ValueError(f"Attribute {attribute} is not an attribute of {owner}")
    #             parent_widget.insertCell(pos, cell)
    #             return cell
        
    # def destroyAttributeWidget(self, parent_widget: NodeWidget|OutletWidget|InletWidget|LinkWidget, widget: CellWidget):
    #     if not isinstance(parent_widget, (NodeWidget, OutletWidget, InletWidget, LinkWidget)):
    #         raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
    #     if not isinstance(widget, CellWidget):
    #         raise TypeError("Widget must be a CellWidget")
        
    #     match parent_widget:
    #         case NodeWidget():
    #             parent_widget.removeSideCell(widget)
    #             widget.deleteLater()
    #         case OutletWidget() | InletWidget() | LinkWidget():
    #             parent_widget.removeCell(widget)
    #             widget.deleteLater()

    # def setAttributeEditorData(self, editor:QWidget, controller:AbstractGraphModel , index:QModelIndex|QPersistentModelIndex):
    #     if isinstance(editor, QLineEdit):
    #         text = controller.attributeData(index, Qt.ItemDataRole.DisplayRole)
    #         editor.setText(text)
    
    # def setModelAttributeData(self, editor:QWidget, controller:AbstractGraphModel, index:QModelIndex|QPersistentModelIndex):
    #     if isinstance(editor, QLineEdit):
    #         text = editor.text()
    #         controller.setAttributeData(index, text, Qt.ItemDataRole.EditRole)
    #     else:
    #         raise TypeError(f"Editor must be a QLineEdit, got {type(editor)} instead.")
