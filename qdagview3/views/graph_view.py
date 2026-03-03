##################
# The Graph View #
##################

from __future__ import annotations

from typing import *
from enum import Enum
from dataclasses import dataclass


import logging
import warnings

import networkx as nx

logger = logging.getLogger(__name__)

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

# from ..core import GraphDataRole, GraphItemType, GraphMimeType, indexToPath, indexFromPath

# from qdagview3.models.abstract_graph_model import AbstractGraphModel
# from qdagview3.models.graph_selection_model import GraphSelectionModel
# from qdagview3.models.graph_references import (
#     NodeRef, OutletRef, InletRef, LinkRef, AttributeRef)

from qdagview3.views.utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter

from qdagview3.views.delegates.tree_graph_delegate import TreeGraphDelegate
# from qdagview2.views.delegates.abstract_graph_widget_factory import AbstractGraphWidgetFactory #TODO: merge into delegate
# from qdagview2.views.delegates.graph_widget_factory import GraphWidgetFactory #TODO: merge into delegate

from qdagview3.views.widgets.node_widget import NodeWidget
from qdagview3.views.widgets.port_widget import InletWidget, OutletWidget
from qdagview3.views.widgets.link_widget import LinkWidgetStraight as LinkWidget
from qdagview3.views.widgets.cell_widget import CellWidget

from qdagview3.views.utils.qt import blockingSignals
from qdagview3.views.utils.widget_manager_using_bidict import BiDictWidgetManager
from qdagview3.views.utils.widget_manager_using_persistent_index import PersistentIndexWidgetManager
from qdagview3.views.utils.linking_tool import LinkingTool

from bidict import bidict

from qdagview3.utils.qtutils import indexToPath, indexFromPath

from qdagview3.models.link_model import LinkModel


class GraphView(QGraphicsView):
    def __init__(self, 
                 delegate:TreeGraphDelegate|None=None, 
                 parent: QWidget | None = None):
        super().__init__(parent=parent)


        assert isinstance(delegate, TreeGraphDelegate) or delegate is None, f"Invalid delegate, got: {delegate}"
        self._delegate = delegate if delegate else TreeGraphDelegate()       

        ## graph model (TODO: this should be called the graphmodel, not the controller)
        self._links_model: LinkModel | None = None
        self._links_model_connections: list[tuple[Signal, Callable]] = []
        self._nodes_model_connections: list[tuple[Signal, Callable]] = []
        self._nodes_selection_model:QItemSelectionModel | None = None
        self._node_selection_connections: list[tuple[Signal, Callable]] = []

        ## State of the graph view
        self._linking_tool = LinkingTool(self)

        self._delegate = delegate if delegate else TreeGraphDelegate()
        self._delegate.portPositionChanged.connect(self.handlePortPositionChanged)

        # Widget Managers
        self._row_widget_manager = PersistentIndexWidgetManager()
        self._cell_widget_manager = PersistentIndexWidgetManager()

        # setup the view
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # create a scene
        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)

    def setModel(self, link_model:LinkModel):
        assert isinstance(link_model, LinkModel), f"Expected model of type LinkModel, got {type(link_model)}"
        # Disconnect old model signals
        if self._links_model is not None:
            nodes_model = self._links_model.nodesModel()
            if nodes_model is not None:
                for signal, slot in self._nodes_model_connections:
                    signal.disconnect(slot)
            
            for signal, slot in self._links_model_connections:
                signal.disconnect(slot)

            self._links_model = None
            self._links_model_connections = []

        # connect new model signals
        if link_model is not None:
            nodes_model = link_model.nodesModel()
            if nodes_model is not None:
                nodes_model_connections = [
                    # (nodes_model.modelAboutToBeReset,    self.handleNodesAboutToBeReset),
                    # (nodes_model.modelReset,             self.handleNodesReset),
                    # (nodes_model.rowsAboutToBeInserted,  self.handleNodesAboutToBeInserted),
                    (nodes_model.rowsInserted,            self.handleNodesInserted),
                    (nodes_model.rowsAboutToBeRemoved,    self.handleNodesAboutToBeRemoved),
                    (nodes_model.columnsInserted,         self.handleNodesColumnsInserted),
                    (nodes_model.columnsAboutToBeRemoved, self.handleNodesColumnsAboutToBeRemoved),
                    # (nodes_model.rowsRemoved,            self.handleNodesRemoved),
                    (nodes_model.dataChanged,            self.handleNodesDataChanged),
                ]
                for signal, slot in nodes_model_connections:
                    signal.connect(slot)
                self._nodes_model_connections = nodes_model_connections

            links_model_connections: list[tuple[pyqtBoundSignal, Callable]] = []
            links_model_connections = [
                # (link_model.modelAboutToBeReset,   self.handleLinksAboutToBeReset),
                # (link_model.modelReset,            self.handleLinksReset),
                # (link_model.rowsAboutToBeInserted, self.handleLinksAboutToBeInserted),
                (link_model.rowsInserted,          self.handleLinksInserted),
                (link_model.rowsAboutToBeRemoved,  self.handleLinksAboutToBeRemoved),
                # (link_model.rowsRemoved,           self.handleLinksRemoved),
                # (link_model.dataChanged,           self.handleLinksDataChanged),
            ]
            for signal, slot in links_model_connections:
                signal.connect(slot)
            self._links_model_connections = links_model_connections
            self._links_model = link_model

        # Set the controller for the linking tool
        self._linking_tool.setController(link_model)

        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._row_widget_manager.clear()
        self._cell_widget_manager.clear()

        self.handleNodesInserted(QModelIndex(), 0, self._links_model.nodesModel().rowCount(QModelIndex()) - 1)

    ## Handle model changes / Manage widget lifecycle        
    def handleNodesInserted(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"


        for row in range(first, last + 1):
            row_index = nodes_model.index(row, 0, parent)
            if not parent.isValid():
                # This is a top-level node
                scene = self.scene()
                assert scene is not None
                row_widget = self._delegate.createRowWidget(scene, row_index)
            else:
                # This is a child node, so we need to find the parent widget
                parent_widget = self._row_widget_manager.getWidget(parent)
                assert parent_widget is not None, f"Failed to find parent widget for index: {parent}"
                row_widget = self._delegate.createRowWidget(parent_widget, row_index)

            self._row_widget_manager.insertWidget(row_index, row_widget)

            # create cell widgets
            column_count = nodes_model.columnCount(row_index)
            self.handleCellsInserted(row_index, 0, column_count - 1)

            # Now that the row widget is created, we can create widgets for the child nodes recursively
            children_count = nodes_model.rowCount(row_index)
            self.handleNodesInserted(row_index, 0, children_count - 1)

    def handleNodesAboutToBeRemoved(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node removals!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for row in range(first, last + 1):
            row_index = nodes_model.index(row, 0, parent)
            if not parent.isValid():
                # This is a top-level node
                row_widget = self._row_widget_manager.getWidget(row_index)
                assert row_widget is not None, f"Failed to find widget for index: {row_index}"
            else:
                # This is a child node, so we need to find the parent widget
                parent_widget = self._row_widget_manager.getWidget(parent)
                assert parent_widget is not None, f"Failed to find parent widget for index: {parent}"
                row_widget = self._row_widget_manager.getWidget(row_index)
                assert row_widget is not None, f"Failed to find widget for index: {row_index}"

            # First remove widgets for child nodes recursively
            children_count = nodes_model.rowCount(row_index)
            self.handleNodesAboutToBeRemoved(row_index, 0, children_count - 1)

            # Then remove cell widgets
            column_count = nodes_model.columnCount(row_index)
            self.handleCellsRemoved(row_index, 0, column_count - 1)

            # Finally remove the row widget itself
            if scene := row_widget.scene():
                scene.removeItem(row_widget)
            self._row_widget_manager.removeWidget(row_index)

    def handleNodesColumnsInserted(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for column in range(first, last + 1):
            cell_index = nodes_model.index(0, column, parent)
            assert cell_index.isValid(), f"Invalid cell index: {cell_index}"

            # For each row in the parent index, we need to insert a cell widget for the new column
            for row in range(nodes_model.rowCount(parent)):
                row_index = nodes_model.index(row, 0, parent)
                assert row_index.isValid(), f"Invalid row index: {row_index}"
                cell_index = nodes_model.index(row, column, parent)
                assert cell_index.isValid(), f"Invalid cell index: {cell_index}"
                row_widget = self._row_widget_manager.getWidget(row_index)
                cell_widget = self._delegate.createCellWidget(row_widget, cell_index)
                self._cell_widget_manager.insertWidget(cell_index, cell_widget)

    def handleNodesColumnsAboutToBeRemoved(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for column in range(first, last + 1):
            cell_index = nodes_model.index(0, column, parent)
            assert cell_index.isValid(), f"Invalid cell index: {cell_index}"

            # For each row in the parent index, we need to remove the cell widget for the removed column
            for row in range(nodes_model.rowCount(parent)):
                row_index = nodes_model.index(row, 0, parent)
                assert row_index.isValid(), f"Invalid row index: {row_index}"
                cell_index = nodes_model.index(row, column, parent)
                assert cell_index.isValid(), f"Invalid cell index: {cell_index}"
                if cell_widget := self._cell_widget_manager.getWidget(cell_index):
                    row_widget = self._row_widget_manager.getWidget(row_index)
                    self._delegate.destroyCellWidget(row_widget, cell_widget)
                    self._cell_widget_manager.removeWidget(cell_index)

    def handleCellsInserted(self, row_index:QModelIndex, first:int, last:int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        row_widget = self._row_widget_manager.getWidget(row_index)
        assert row_widget is not None, f"Failed to find row widget for index: {row_index}"
        for column in range(first, last + 1):
            cell_index = nodes_model.index(row_index.row(), column, row_index.parent())
            assert row_index.isValid(), f"Invalid row index: {row_index}"
            assert cell_index.isValid(), f"Invalid cell index: {cell_index}"

            cell_widget = self._delegate.createCellWidget(row_widget, cell_index)
            self._cell_widget_manager.insertWidget(cell_index, cell_widget)

    def handleCellsRemoved(self, row_index:QModelIndex, first:int, last:int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        row_widget = self._row_widget_manager.getWidget(row_index)
        assert row_widget is not None, f"Failed to find row widget for index: {row_index}"
        for column in range(first, last + 1):
            cell_index = nodes_model.index(row_index.row(), column, row_index.parent())
            assert row_index.isValid(), f"Invalid row index: {row_index}"
            assert cell_index.isValid(), f"Invalid cell index: {cell_index}"

            if cell_widget := self._cell_widget_manager.getWidget(cell_index):
                self._delegate.destroyCellWidget(row_widget, cell_widget)
                self._cell_widget_manager.removeWidget(cell_index)

    # def handleOutletsInserted(self, outlet_indexes:List[QPersistentModelIndex]):
    #     for outlet_index in outlet_indexes:
    #         w = self._addOutletWidgetForIndex(outlet_index)
    #         assert w is not None, f"Failed to create widget for outlet index: {outlet_index}"
    #         self.handleAttributesInserted(self._links_model.attributes(outlet_index))

    # def handleInletsInserted(self, inlet_indexes:List[QPersistentModelIndex]):
    #     for inlet_index in inlet_indexes:
    #         w = self._addInletWidgetForIndex(inlet_index)
    #         assert w is not None, f"Failed to create widget for inlet index: {inlet_index}"
    #         self.handleAttributesInserted(self._links_model.attributes(inlet_index))

    def handleLinksInserted(self, link_indexes:List[QPersistentModelIndex]):
        for link_index in link_indexes:
            w = self._addLinkWidgetForIndex(link_index)
            assert w is not None, f"Failed to create widget for link index: {link_index}"
            self.handleAttributesInserted(self._links_model.attributes(link_index))

    # def handleAttributesInserted(self, attributes:List[QPersistentModelIndex]):
    #     for attribute in attributes:
    #         self._addCellWidgetForIndex(attribute)

    # def handleNodesRemoved(self, node_indexes:List[QPersistentModelIndex]):
    #     for node_index in node_indexes:
    #         self.handleInletsRemoved(self._links_model.inlets(node_index))
    #         self.handleOutletsRemoved(self._links_model.outlets(node_index))
    #         self.handleAttributesRemoved(self._links_model.attributes(node_index))
    #         self._removeNodeWidgetForIndex(node_index)

    # def handleInletsRemoved(self, inlet_indexes:List[QPersistentModelIndex]):
    #     for inlet_index in inlet_indexes:
    #         for link in self._links_model.links(inlet_index):
    #             self.handleAttributesRemoved(self._links_model.attributes(link))
    #             self._removeLinkWidgetForIndex(link)
    #         self._removeInletWidgetForIndex(inlet_index)

    # def handleOutletsRemoved(self, outlet_indexes:List[QPersistentModelIndex]):
    #     for outlet_index in outlet_indexes:
    #         for link in self._links_model.links(outlet_index):
    #             self.handleAttributesRemoved(self._links_model.attributes(link))
    #             self._removeLinkWidgetForIndex(link)
    #         self._removeOutletWidgetForIndex(outlet_index)

    def handleLinksAboutToBeRemoved(self, link_indexes:List[QPersistentModelIndex]):
        for link_index in link_indexes:
            self.handleAttributesRemoved(self._links_model.attributes(link_index))
            self._removeLinkWidgetForIndex(link_index)

    # def handleAttributesRemoved(self, attributes:List[QPersistentModelIndex]):
    #     for attribute in reversed(attributes):
    #         self._removeCellWidgetForIndex(attribute)



    # def model(self) -> QAbstractItemModel | None:
    #     return self._item_model
    
    ## Index lookup
    def rowAt(self, point:QPoint, filter_type:GraphItemType|None=None) -> GraphT|NodeT|PortT|LinkT|None:
        all_widgets = set(self._row_widget_manager.widgets())
        for item in self.items(point):
            if item in all_widgets:
                index = self._row_widget_manager.getIndex(item)
                if filter_type is None:
                    return index
                else:
                    if self._links_model.itemType(index) == filter_type:
                        return index
        return None
    
    def attributeAt(self, point:QPoint) -> AttributeRef|None:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_widget_manager.widgets())
        for item in self.items(point):
            if item in all_cells:
                return self._cell_widget_manager.getIndex(item)
        return None

    def handlePortPositionChanged(self, port_index:PortT):
        """Reposition all links connected to the moved port widget."""
        assert self._links_model, "Model must be set before handling port position changes!"
        link_indexes = self._links_model.links(port_index)
        for link_index in link_indexes:
            if link_widget := self._row_widget_manager.getWidget(link_index):
                source_index = self._links_model.linkSource(link_index)
                source_widget = self._row_widget_manager.getWidget(source_index)
                target_index = self._links_model.linkTarget(link_index)
                target_widget = self._row_widget_manager.getWidget(target_index)
                if source_widget and target_widget:
                    self._update_link_position(link_widget, source_widget, target_widget)

    def _update_link_position(self, link_widget:LinkWidgetStraight, source_widget:QGraphicsItem|None=None, target_widget:QGraphicsItem|None=None):
        # Compute the link geometry in the link widget's local coordinates.
        if source_widget and target_widget:
            line = makeLineBetweenShapes(source_widget, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)

        elif source_widget:
            source_center = getShapeCenter(source_widget)
            source_size = source_widget.boundingRect().size()
            origin = QPointF(source_center.x() - source_size.width()/2, source_center.y() - source_size.height()/2)+QPointF(24,24)
            line = makeLineToShape(origin, source_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            line = QLineF(line.p2(), line.p1())  # Reverse the line direction
            link_widget.setLine(line)

        elif target_widget:
            target_center = getShapeCenter(target_widget)
            target_size = target_widget.boundingRect().size()
            origin = QPointF(target_center.x() - target_size.width()/2, target_center.y() - target_size.height()/2)-QPointF(24,24)
            line = makeLineToShape(origin, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)
        else:
            ...

        link_widget.update()

    # ## Manage widgets
    # def _addNodeWidgetForIndex(self, row_index:NodeRef)->QGraphicsItem:
    #     # widget management
    #     row_widget = self._delegate.createRowWidget(self.scene(), row_index, self)
    #     print(f"Created widget for node index: {row_index}, widget: {row_widget}")
    #     self._row_widget_manager.insertWidget(row_index, row_widget)

    #     return row_widget
    
    # def _addOutletWidgetForIndex(self, row_index:OutletRef)->QGraphicsItem:
    #     assert self._links_model, "Model must be set before adding outlet widgets!"
    #     node_index = self._links_model.outletNode(row_index)  # ensure outlet node is valid

    #     parent_node_widget = self._row_widget_manager.getWidget(node_index)

    #     # widget delegate
    #     row_widget = self._delegate.createOutletWidget(parent_node_widget, row_index, self)

    #     # widget management
    #     print(f"Adding outlet widget for outlet index: {row_index}, parent node index: {node_index}")
    #     self._row_widget_manager.insertWidget(row_index, row_widget)

    #     return row_widget

    # def _addInletWidgetForIndex(self, row_index:InletRef)->QGraphicsItem:
    #     assert self._links_model, "Model must be set before adding inlet widgets!"
    #     node_index = self._links_model.inletNode(row_index)  # ensure inlet node is valid
    #     parent_node_widget = self._row_widget_manager.getWidget(node_index)

    #     # widget delegate
    #     row_widget = self._delegate.createInletWidget(parent_node_widget, row_index, self)

    #     # widget management
    #     print(f"Adding inlet widget for inlet index: {row_index}, parent node index: {node_index}")
    #     self._row_widget_manager.insertWidget(row_index, row_widget)

    #     return row_widget

    # def _addLinkWidgetForIndex(self, link_ref:LinkRef)->QGraphicsItem:
    #     assert self._links_model, "Model must be set before adding link widgets!"
    #     inlet_index = self._links_model.linkTarget(link_ref)  # ensure target is valid
    #     parent_inlet_widget = self._row_widget_manager.getWidget(inlet_index)
    #     assert isinstance(parent_inlet_widget, InletWidget)

    #     # link management
    #     source_index = self._links_model.linkSource(link_ref)
    #     source_widget = self._row_widget_manager.getWidget(source_index) if source_index is not None else None
    #     target_index = self._links_model.linkTarget(link_ref)
    #     target_widget = self._row_widget_manager.getWidget(target_index) if target_index is not None else None
        
    #     # widget delegate
    #     link_widget = self._delegate.createLinkWidget(source_widget, target_widget, link_ref, self)

    #     # widget management
    #     print(f"Adding link widget for link index: {link_ref}, target inlet index: {inlet_index}")
    #     self._row_widget_manager.insertWidget(link_ref, link_widget)
    #     self._update_link_position(link_widget, source_widget, target_widget)

    #     return link_widget

    # def _addCellWidgetForIndex(self, cell_index:QPersistentModelIndex)->QGraphicsItem:
    #     row_index = self._links_model.attributeOwner(cell_index)
    #     row_widget = self._row_widget_manager.getWidget(row_index)
    #     cell_widget = self._delegate.createAttributeWidget(row_widget, cell_index, self)
    #     print(f"Adding cell widget for attribute index: {cell_index}, parent row index: {row_index}")
    #     self._cell_widget_manager.insertWidget(cell_index, cell_widget)
    #     self._set_cell_data(cell_index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
    #     return cell_widget

    # def _removeNodeWidgetForIndex(self, row_index:NodeT):
    #     # widget management
    #     if row_widget := self._row_widget_manager.getWidget(row_index):
    #         self._delegate.destroyRowWidget(self.scene(), row_widget)
    #         self._row_widget_manager.removeWidget(row_index)

    # def _removeInletWidgetForIndex(self, row_index:QPersistentModelIndex):    
    #     # widget management
    #     if row_widget := self._row_widget_manager.getWidget(row_index):
    #         node_index = self._links_model.inletNode(row_index)
    #         parent_widget = self._row_widget_manager.getWidget(node_index)
    #         self._delegate.destroyInletWidget(parent_widget, row_widget)
    #         self._row_widget_manager.removeWidget(row_index)

    # def _removeOutletWidgetForIndex(self, row_index:QPersistentModelIndex):
    #     # widget management
    #     if row_widget := self._row_widget_manager.getWidget(row_index):
    #         node_index = self._links_model.outletNode(row_index)
    #         parent_widget = self._row_widget_manager.getWidget(node_index)
    #         self._delegate.destroyOutletWidget(parent_widget, row_widget)
    #         self._row_widget_manager.removeWidget(row_index)
    
    # def _removeLinkWidgetForIndex(self, link_index:QPersistentModelIndex):
    #     # widget management
    #     if link_widget := self._row_widget_manager.getWidget(link_index):
    #         self._delegate.destroyLinkWidget(self.scene(), link_widget)
    #         self._row_widget_manager.removeWidget(link_index)
    
    # def _removeCellWidgetForIndex(self, cell_index:QPersistentModelIndex):
    #     if cell_widget := self._cell_widget_manager.getWidget(cell_index):
    #         row_index = self._links_model.attributeOwner(cell_index)
    #         row_widget = self._row_widget_manager.getWidget(row_index)
    #         self._delegate.destroyAttributeWidget(row_widget, cell_widget)
    #         self._cell_widget_manager.removeWidget(cell_index)

    # def _addNodeColumnWidgetForIndex(self, node_ref:NodeRef, column:int)->QGraphicsItem:
    #     node_widget = self._row_widget_manager.getWidget(node_ref)
    #     column_widget = self._delegate.createNodeColumnWidget(node_widget, node_ref, column, self)
    #     self._column_widget_manager.insertWidget((node_ref, column), column_widget)
    #     return column_widget
    
    # def _removeNodeColumnWidgetForIndex(self, node_ref:NodeRef, column:int):
    #     if column_widget := self._column_widget_manager.getWidget((node_ref, column)):
    #         self._delegate.destroyNodeColumnWidget(column_widget)
    #         self._column_widget_manager.removeWidget((node_ref, column))

    ## Handle attributes data changes
    def handleNodesDataChanged(self, topleft:QModelIndex, bottomright:QModelIndex, roles:List[int]):
        assert self._links_model is not None, "Model must be set before handling node data changes!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"
        print(f"Handling node data changed, topleft: {topleft}, bottomright: {bottomright}, roles: {roles}")
        for col in range(topleft.column(), bottomright.column() + 1):
            for row in range(topleft.row(), bottomright.row() + 1):
                cell_index = nodes_model.index(row, col, topleft.parent())
                if cell_widget:=self._cell_widget_manager.getWidget(cell_index):
                    self._delegate.setCellEditorData(cell_widget, cell_index)

    def handleAttributeDataChanged(self, attributes:List[QPersistentModelIndex], roles:List[int]):
        for attribute in attributes:
            self._set_cell_data(attribute, roles)

    def _set_cell_data(self, index:QPersistentModelIndex, roles:list=[]):
        """Set the data for a cell widget."""
        # assert index.isValid(), "Index must be valid"

        if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.DisplayRole in roles or roles == []:
            if cell_widget:= self._cell_widget_manager.getWidget(index):
                text = self._links_model.attributeData(index, role=Qt.ItemDataRole.DisplayRole)
                cell_widget.setText(f"{text}")

    ## Selection handling   
    def setSelectionModel(self, graph_selection_model: GraphSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(graph_selection_model, GraphSelectionModel), f"got: {graph_selection_model}"
        assert self._links_model, "Model must be set before setting the selection model!"
        assert graph_selection_model.graphModel() == self._links_model, "Selection model must be for the same model as the graph view!"
        
        if self._nodes_selection_model:
            for signal, slot in self._node_selection_connections:
                signal.disconnect(slot)
            self._node_selection_connections = []
        
        if graph_selection_model:
            self._node_selection_connections = [
                (graph_selection_model.selectionChanged, self._handleSelectionChanged),
                (graph_selection_model.currentChanged, self._handleCurrentChanged),
            ]
            for signal, slot in self._node_selection_connections:
                signal.connect(slot)

        self._nodes_selection_model = graph_selection_model
        
        scene = self.scene()
        assert scene is not None
        scene.selectionChanged.connect(self._syncSelectionController)

    def selectionModel(self) -> GraphSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._nodes_selection_model
    
    @Slot(list, list)
    def _handleSelectionChanged(self, selected:list, deselected:list):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        assert self._nodes_selection_model, "Selection model must be set before handling selection changes!"
        assert self._links_model, "Model must be set before handling selection changes!"
        assert self._nodes_selection_model.graphModel() == self._links_model, "Selection model must be for the same model as the graph view!"
        if not selected and not deselected:
            return
        scene = self.scene()
        assert scene is not None

        with blockingSignals(scene):           
            for index in deselected:
                if index.isValid():
                    if widget:=self._row_widget_manager.getWidget(index):
                        if widget.scene() and widget.isSelected():
                            widget.setSelected(False)
                            
            for index in selected:
                if index.isValid():
                    if widget:=self._row_widget_manager.getWidget(index):
                        if widget.scene() and not widget.isSelected():
                            widget.setSelected(True)
            # selected_indexes = sorted([idx for idx in selected], 
            #                         key= lambda idx: idx.row(), 
            #                         reverse= True)
            
            # deselected_indexes = sorted([idx for idx in deselected], 
            #                             key= lambda idx: idx.row(), 
            #                             reverse= True)
            
            # for index in deselected_indexes:
            #     if index.isValid() and index.column() == 0:
            #         if widget:=self._widget_manager.getWidget(index):
            #             if widget.scene() and widget.isSelected():
            #                 widget.setSelected(False)

            # for index in selected_indexes:
            #     if index.isValid() and index.column() == 0:
            #         if widget:=self._widget_manager.getWidget(index):
            #             if widget.scene() and not widget.isSelected():
            #                 widget.setSelected(True)

    def _handleCurrentChanged(self, current:NodeT|LinkT, previous:NodeT|LinkT):
        ...

    def _syncSelectionController(self):
        """update selection controller from scene selection"""
        print("Syncing selection controller from scene selection...")
        scene = self.scene()
        assert scene is not None
        if self._links_model and self._nodes_selection_model:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to nodeT
            selected_indexes = map(self._row_widget_manager.getIndex, selected_widgets)
            selected_indexes = list(filter(lambda idx: idx is not None and idx.isValid(), selected_indexes))
            
            assert self._links_model, "Model must be set before syncing selection!"
            # def selectionFromIndexes(selected_indexes:Iterable[QModelIndex]) -> QItemSelection:
            #     """Create a QItemSelection from a list of selected indexes."""
            #     item_selection = QItemSelection()
            #     for index in selected_indexes:
            #         if index.isValid():
            #             item_selection.select(index, index)
                
            #     return item_selection
            # item_selection = selectionFromIndexes(selected_indexes)

            # perform selection on model
            
            self._nodes_selection_model.select(selected_indexes, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(selected_indexes) > 0:
                last_selected_index = selected_indexes[-1]
                self._nodes_selection_model.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
            else:
                self._nodes_selection_model.clearSelection()
                self._nodes_selection_model.setCurrentIndex(None, QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows)

    ## Handle mouse events
    def mousePressEvent(self, event:QMouseEvent):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        if self._linking_tool.isActive():
            # If we are already linking, cancel the linking operation
            self._linking_tool.cancelLinking()
            return

        # get the index at the mouse position
        pos = event.position()
        index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))
        scene_pos = self.mapToScene(event.position().toPoint())
        row_widget = self._row_widget_manager.getWidget(index)
        print(f"Mouse press at position: {event.position()}, scene position: {scene_pos}, index: {index}, row widget: {row_widget}")
        # If we can start linking, do so
        if index and self._delegate.canStartLink(row_widget, index, event):
            self._linking_tool.startLinking(index, scene_pos)
        else:
            # Fallback to default behavior
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._linking_tool.isActive():
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            self._linking_tool.updateLinking(pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._linking_tool.isActive():
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            drop_target = self.rowAt(pos)  # Ensure the index is updated
            if not self._linking_tool.finishLinking(drop_target):
                # Handle failed linking
                logger.warning("WARNING: Linking failed!")
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        assert self._links_model, "Model must be set before handling double click!"
        index = self.attributeAt(QPoint(int(event.position().x()), int(event.position().y())))
        

        if index is None or not index.isValid():
            idx = self._links_model.addNode(None)
            if widget := self._row_widget_manager.getWidget(idx):
                center = widget.boundingRect().center()
                widget.setPos(self.mapToScene(event.position().toPoint())-center)

            return
            
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelAttributeData(editor, self._links_model, index)
            editor.deleteLater()
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if cell_widget := self._cell_widget_manager.getWidget(index):
            option = QStyleOptionViewItem()
            scene_rect = cell_widget.mapRectToScene(cell_widget.boundingRect())
            view_poly:QPolygon = self.mapFromScene(scene_rect)
            rect = view_poly.boundingRect()
            option.rect = rect
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            
            editor = self._delegate.createEditor(self, option, self._links_model, index)
            if editor:
                # Ensure the editor is properly positioned and shown
                editor.setParent(self)
                editor.setGeometry(rect)
                self._delegate.setAttributeEditorData(editor, index)
                editor.show()  # Explicitly show the editor
                editor.setFocus(Qt.FocusReason.MouseFocusReason)
                editor.editingFinished.connect(lambda editor=editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index))

    # def dragEnterEvent(self, event)->None:
    #     if event.mimeData().hasFormat(GraphMimeType.InletData) or event.mimeData().hasFormat(GraphMimeType.OutletData):
    #         # Create a draft link if the mime data is for inlets or outlets
            
    #         event.acceptProposedAction()

    #     if event.mimeData().hasFormat(GraphMimeType.LinkHeadData) or event.mimeData().hasFormat(GraphMimeType.LinkTailData):
    #         # Create a draft link if the mime data is for link heads or tails
    #         event.acceptProposedAction()

    # def dragLeaveEvent(self, event):
    #     if self._draft_link:
    #         scene = self.scene()
    #         assert scene is not None
    #         scene.removeItem(self._draft_link)
    #         self._draft_link = None
    #     #self._cleanupDraftLink()  # Cleanup draft link if it exists
    #     # super().dragLeaveEvent(event)
    #     # self._cleanupDraftLink()

    # def dragMoveEvent(self, event)->None:
    #     """Handle drag move events to update draft link position"""
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates

    #     data = event.mimeData()
    #     payload = Payload.fromMimeData(data)
        
    #     self.updateLinking(payload, pos)
    #     return

    # def dropEvent(self, event: QDropEvent) -> None:
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
    #     drop_target = self.rowAt(pos)  # Ensure the index is updated

    #     # TODO: check for drag action
    #     # match event.proposedAction():
    #     #     case Qt.DropAction.CopyAction:
    #     #         ...
    #     #     case Qt.DropAction.MoveAction:
    #     #         ...
    #     #     case Qt.DropAction.LinkAction:
    #     #         ...
    #     #     case Qt.DropAction.IgnoreAction:
    #     #         ...
        
    #     if self.finishLinking(event.mimeData(), drop_target):
    #         event.acceptProposedAction()
    #     else:
    #         event.ignore()

