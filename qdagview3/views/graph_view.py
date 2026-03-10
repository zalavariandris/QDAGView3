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

from qtpy.QtCore import (
    QObject, 
    Qt, 
    Signal, 
    Slot, 
    QModelIndex, 
    QItemSelectionModel, 
    QItemSelection, 
    QPersistentModelIndex,
    QPoint,
    QEvent,
    QRectF,
    QPointF,
    QLineF
)
from qtpy.QtGui import (
    QPainter, 
    QPen, 
    QBrush, 
    QColor, 
    QTransform, 
    QMouseEvent, 
    QWheelEvent, 
    QKeyEvent, 
    QContextMenuEvent, 
    QDragEnterEvent, 
    QDragMoveEvent, 
    QDropEvent, 
    QPainterPath, 
    QPolygonF, 
    QPainterPath, 
    QCursor, 
    QFont, 
    QFontMetrics, 
    QPixmap,

    
)
from qtpy.QtWidgets import (
    QGraphicsView, 
    QGraphicsScene, 
    QGraphicsItem, 
    QGraphicsLineItem, 
    QGraphicsPathItem, 
    QGraphicsPolygonItem, 
    QWidget, 
    QStyleOptionViewItem,
    QLineEdit,
    QStyle
)

# from ..core import GraphDataRole, GraphItemType, GraphMimeType, indexToPath, indexFromPath

# from qdagview3.models.abstract_graph_model import AbstractGraphModel
# from qdagview3.models.graph_selection_model import GraphSelectionModel
# from qdagview3.models.graph_references import (
#     NodeRef, OutletRef, InletRef, LinkRef, AttributeRef)

from qdagview3.views.utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter


from qdagview3.delegates.abstract_graph_delegate import AbstractGraphDelegate
from qdagview3.delegates.tree_graph_delegate import TreeGraphDelegate
# from qdagview2.views.delegates.abstract_graph_widget_factory import AbstractGraphWidgetFactory #TODO: merge into delegate
# from qdagview2.views.delegates.graph_widget_factory import GraphWidgetFactory #TODO: merge into delegate

# from qdagview3.views.widgets.node_widget import NodeWidget
# from qdagview3.views.widgets.port_widget import InletWidget, OutletWidget
# from qdagview3.views.widgets.link_widget import LinkWidgetStraight as LinkWidget
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
                 delegate:AbstractGraphDelegate|None=None, 
                 parent: QWidget | None = None):
        super().__init__(parent=parent)


        assert isinstance(delegate, AbstractGraphDelegate) or delegate is None, f"Invalid delegate, got: {delegate}"   
        self._delegate = delegate if delegate else TreeGraphDelegate()
        self._delegate.portPositionChanged.connect(self._on_port_position_changed)

        ## - models -
        self._links_model: LinkModel | None = None
        self._links_model_connections: list[tuple[Signal, Callable]] = []
        self._nodes_model_connections: list[tuple[Signal, Callable]] = []
        self._nodes_selection_model:QItemSelectionModel | None = None
        self._nodes_selection_connections: list[tuple[Signal, Callable]] = []
        self._links_selection_model:QItemSelectionModel | None = None
        self._links_selection_connections: list[tuple[Signal, Callable]] = []

        ## State of the graph view
        # self._linking_tool = LinkingTool(self)
        self._interaction_mode: Literal[None, "LINKING"] = None
        self._interaction_payload: Tuple[Any, Literal['outlet', 'inlet', 'tail', 'head']] = None
        self._draft_link = None
        self._active_editor: QWidget | None = None
        self._active_editor_index: QPersistentModelIndex | None = None

        # Widget Managers
        self._row_widget_manager = PersistentIndexWidgetManager()
        self._link_widget_manager = PersistentIndexWidgetManager()
        self._cell_widget_manager = PersistentIndexWidgetManager()

        self._is_column_hidden: dict[int, bool] = {}

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
                    (nodes_model.rowsInserted,            self._on_nodes_inserted),
                    (nodes_model.rowsAboutToBeRemoved,    self._on_nodes_about_to_be_removed),
                    (nodes_model.columnsInserted,         self._on_nodes_columns_inserted),
                    (nodes_model.columnsAboutToBeRemoved, self._on_nodes_columns_about_to_be_removed),
                    # (nodes_model.rowsRemoved,            self.handleNodesRemoved),
                    
                    (nodes_model.dataChanged,             self._on_nodes_data_changed),
                    (nodes_model.headerDataChanged,       self._on_nodes_header_data_changed),
                ]
                for signal, slot in nodes_model_connections:
                    signal.connect(slot)
                self._nodes_model_connections = nodes_model_connections

            links_model_connections: list[tuple[Signal, Callable]] = []
            links_model_connections = [
                # (link_model.modelAboutToBeReset,   self.handleLinksAboutToBeReset),
                # (link_model.modelReset,            self.handleLinksReset),
                # (link_model.rowsAboutToBeInserted, self.handleLinksAboutToBeInserted),
                (link_model.rowsInserted,          self._on_links_inserted),
                (link_model.rowsAboutToBeRemoved,  self._on_links_about_to_be_removed),
                # (link_model.rowsRemoved,           self.handleLinksRemoved),
                (link_model.dataChanged,           self._on_links_data_changed),
            ]
            for signal, slot in links_model_connections:
                signal.connect(slot)
            self._links_model_connections = links_model_connections
            self._links_model = link_model

        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._row_widget_manager.clear()
        self._link_widget_manager.clear()
        self._cell_widget_manager.clear()

        self._on_nodes_inserted(QModelIndex(), 0, self._links_model.nodesModel().rowCount(QModelIndex()) - 1)
        self._on_links_inserted(QModelIndex(), 0, self._links_model.rowCount(QModelIndex()) - 1)
    
    ## Handle model changes / Manage widget lifecycle        
    def _on_nodes_inserted(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for row in range(first, last + 1):
            row_index = nodes_model.index(row, 0, parent)
            if not parent.isValid():
                # This is a top-level node
                row_widget = self._delegate.createRowWidget(None, row_index)
                scene = self.scene()
                assert scene is not None
                scene.addItem(row_widget)
            else:
                # This is a child node, so we need to find the parent widget
                parent_widget = self._row_widget_manager.getWidget(parent)
                assert parent_widget is not None, f"Failed to find parent widget for index: {parent}"
                row_widget = self._delegate.createRowWidget(parent_widget, row_index)
                
                scene = self.scene()
                assert scene is not None
                scene.addItem(row_widget)

            self._row_widget_manager.insertWidget(row_index, row_widget)

            # create cell widgets
            column_count = nodes_model.columnCount(row_index.parent())
            self._handle_cells_inserted(row_index, 0, column_count - 1) # Note: Start from column1 to skip the title column which is handled by the row widget itself

            # Now that the row widget is created, we can create widgets for the child nodes recursively
            children_count = nodes_model.rowCount(row_index)
            self._on_nodes_inserted(row_index, 0, children_count - 1)

    def _on_nodes_about_to_be_removed(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node removals!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for row in range(first, last + 1):
            row_index = nodes_model.index(row, 0, parent)
            if not parent.isValid():
                # This is a top-level node
                row_widget = self._row_widget_manager.getWidget(row_index)
                assert row_widget is not None, f"Failed to find widget for index: {row_index}"
                self._delegate.destroyRowWidget(None, row_widget, row_index)
            else:
                # This is a child node, so we need to find the parent widget
                parent_widget = self._row_widget_manager.getWidget(parent)
                assert parent_widget is not None, f"Failed to find parent widget for index: {parent.row()}"
                row_widget = self._row_widget_manager.getWidget(row_index)
                assert row_widget is not None, f"Failed to find row widget for index: {row_index.row()}"
                parent_widget = self._row_widget_manager.getWidget(parent)
                assert parent_widget is not None, f"Failed to find parent widget for index: {parent.row()}"
                self._delegate.destroyRowWidget(parent_widget, row_widget, row_index)
            # First remove widgets for child nodes recursively
            children_count = nodes_model.rowCount(row_index)
            self._on_nodes_about_to_be_removed(row_index, 0, children_count - 1)

            # Then remove cell widgets
            column_count = nodes_model.columnCount(row_index)
            self._handle_cells_removed(row_index, 0, column_count - 1)

            # Finally remove the row widget itself
            if scene := row_widget.scene():
                scene.removeItem(row_widget)
            self._row_widget_manager.removeWidget(row_index)

    def _on_nodes_columns_inserted(self, parent:QModelIndex, first: int, last: int):
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

                print(f"Column inserted: {column}, setting cell widget visibility to: {not self.isColumnHidden(column)}")
                cell_widget.setVisible(not self.isColumnHidden(column))
                


                scene = self.scene()
                assert scene is not None
                if cell_widget.scene() is None:
                    scene.addItem(cell_widget)

    def _on_nodes_columns_about_to_be_removed(self, parent:QModelIndex, first: int, last: int):
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
                    self._delegate.destroyCellWidget(row_widget, cell_widget, cell_index)
                    scene = self.scene()
                    assert scene is not None
                    scene.removeItem(cell_widget)
                    self._cell_widget_manager.removeWidget(cell_index)

    def _handle_cells_inserted(self, row_index:QModelIndex, first:int, last:int):
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
            print(f"Column inserted: {column}, setting cell widget visibility to: {not self.isColumnHidden(column)}")
            cell_widget.setVisible(not self.isColumnHidden(column))
            self._cell_widget_manager.insertWidget(cell_index, cell_widget)
            scene = self.scene()
            assert scene is not None
            scene.addItem(cell_widget)

    def _handle_cells_removed(self, row_index:QModelIndex, first:int, last:int):
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
                self._delegate.destroyCellWidget(row_widget, cell_widget, cell_index)
                self._cell_widget_manager.removeWidget(cell_index)
                scene = self.scene()
                assert scene is not None
                scene.removeItem(cell_widget)

    def _on_links_inserted(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for row in range(first, last + 1):
            link_index = self._links_model.index(row, 0, parent)
            assert link_index.isValid(), f"Invalid link index: {link_index}"
            source_index = self._links_model.linkSource(link_index)
            assert isinstance(source_index, QModelIndex) and source_index.isValid(), f"Invalid source index for link, got: {source_index}"
            target_index = self._links_model.linkTarget(link_index)
            assert isinstance(target_index, QModelIndex) and target_index.isValid(), f"Invalid target index for link, got: {target_index}"
            source_widget = self._row_widget_manager.getWidget(source_index)
            target_widget = self._row_widget_manager.getWidget(target_index)
            link_widget = self._delegate.createLinkWidget(link_index, source_widget, target_widget)
            self._link_widget_manager.insertWidget(link_index, link_widget)
            self._delegate.moveLinkWidget(link_widget, source_widget, target_widget)
            scene = self.scene()
            assert scene is not None
            scene.addItem(link_widget)

    def _on_links_about_to_be_removed(self, parent:QModelIndex, first: int, last: int):
        assert self._links_model, "Model must be set before handling node insertions!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        for row in range(first, last + 1):
            link_index = self._links_model.index(row, 0, parent)
            assert link_index.isValid(), f"Invalid link index: {link_index}"
            link_widget = self._link_widget_manager.getWidget(link_index)
            if link_widget is None:
                continue

            source_index = self._links_model.linkSource(link_index)
            target_index = self._links_model.linkTarget(link_index)
            source_widget = self._row_widget_manager.getWidget(source_index) if source_index.isValid() else None
            target_widget = self._row_widget_manager.getWidget(target_index) if target_index.isValid() else None
            self._delegate.destroyLinkWidget(link_widget, link_index, source_widget, target_widget)
            self._link_widget_manager.removeWidget(link_index)
            scene = self.scene()
            assert scene is not None
            scene.removeItem(link_widget)
    
    def _on_links_data_changed(self, topleft:QModelIndex, bottomright:QModelIndex, roles:List[int]):
        assert self._links_model, "Model must be set before handling link data changes!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"
        # print(f"Handling link data changed, topleft: {topleft}, bottomright: {bottomright}, roles: {roles}")
        for row in range(topleft.row(), bottomright.row() + 1):
            link_index = self._links_model.index(row, 0, topleft.parent())
            assert link_index.isValid(), f"Invalid link index: {link_index}"
            link_widget = self._link_widget_manager.getWidget(link_index)
            if link_widget is None:
                continue

            source_index = self._links_model.linkSource(link_index)
            target_index = self._links_model.linkTarget(link_index)
            source_widget = self._row_widget_manager.getWidget(source_index)
            target_widget = self._row_widget_manager.getWidget(target_index)
            assert source_widget is not None, f"Failed to find source widget for index: {source_index}"
            assert target_widget is not None, f"Failed to find target widget for index: {target_index}"
            assert link_widget is not None, f"Failed to find link widget for index: {link_index}"
            self._delegate.moveLinkWidget(link_widget, source_widget, target_widget)

    ## Index lookup
    def rowAt(self, point:QPoint, filter_type:GraphItemType|None=None) -> QModelIndex|None:
        all_widgets = set(self._row_widget_manager.widgets())
        assert isinstance(point, QPoint), f"Expected point of type QPoint, got: {type(point)}"
        for row_widget in self.items(point):
            if row_widget in all_widgets:
                index = self._row_widget_manager.getIndex(row_widget)
                if filter_type is None:
                    return index
                else:
                    if self._links_model.itemType(index) == filter_type:
                        return index
        return None
    
    def linkAt(self, point:QPoint) -> QModelIndex|None:
        all_widgets = set(self._link_widget_manager.widgets())
        for link_widget in self.items(point):
            if link_widget in all_widgets:
                return self._link_widget_manager.getIndex(link_widget)
        return None

    def cellAt(self, point:QPoint) -> QModelIndex|None:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_widget_manager.widgets())
        for item in self.items(point):
            if item in all_cells:
                return self._cell_widget_manager.getIndex(item)
        return None

    def _on_port_position_changed(self, port_index:QModelIndex):
        """Reposition all links connected to the moved port widget."""
        assert self._links_model, "Model must be set before handling port position changes!"
        link_indexes = self._links_model.linksConnectedTo(port_index)
        # print(f"Port index {port_index} position changed, updating connected links: {link_indexes}")
        for link_index in link_indexes:
            if link_widget := self._link_widget_manager.getWidget(link_index):
                source_index = self._links_model.linkSource(link_index)
                source_widget = self._row_widget_manager.getWidget(source_index)
                target_index = self._links_model.linkTarget(link_index)
                target_widget = self._row_widget_manager.getWidget(target_index)
                if source_widget and target_widget:
                    self._delegate.moveLinkWidget(link_widget, source_widget, target_widget)

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

    def _on_nodes_header_data_changed(self, orientation:Qt.Orientation, first:int, last:int):
        assert self._links_model is not None, "Model must be set before handling node data changes!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        # update node widgets
        for row in range(first, last + 1):
            first_cell_index = nodes_model.index(row, 0, QModelIndex())
            # Note: Currently the row represents a node. But we refer to it by the firt cell index.
            # consider refactoring, to have the first cell index be a direct representation of the node. the subsequent cell would be additional cells.
            # TODO: this needs a proper documentation, and also needs a review.
            
            row_widget = self._row_widget_manager.getWidget(first_cell_index)
            if row_widget:
                nodes_model = self._links_model.nodesModel()
                self._delegate.setHeaderWidgetData(row_widget, first_cell_index)

        
    ## Handle attributes data changes
    def _on_nodes_data_changed(self, topleft:QModelIndex, bottomright:QModelIndex, roles:List[int]):
        assert self._links_model is not None, "Model must be set before handling node data changes!"
        nodes_model = self._links_model.nodesModel()
        assert nodes_model is not None, "Link model must have a valid nodes model"

        # update cell widgets
        for row in range(topleft.row(), bottomright.row() + 1):
            for col in range(topleft.column(), bottomright.column() + 1):
                # update cell widget
                cell_index = nodes_model.index(row, col, topleft.parent())
                if cell_widget:=self._cell_widget_manager.getWidget(cell_index):
                    self._delegate.setCellWidgetData(cell_widget, cell_index)

    # def handleAttributeDataChanged(self, attributes:List[QPersistentModelIndex], roles:List[int]):
    #     for attribute in attributes:
    #         self._set_cell_data(attribute, roles)

    # def _set_cell_data(self, index:QPersistentModelIndex, roles:list=[]):
    #     """Set the data for a cell widget."""
    #     # assert index.isValid(), "Index must be valid"

    #     if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.DisplayRole in roles or roles == []:
    #         if cell_widget:= self._cell_widget_manager.getWidget(index):
    #             text = self._links_model.attributeData(index, role=Qt.ItemDataRole.DisplayRole)
    #             cell_widget.setText(f"{text}")

    ## Selection handling   
    def setNodesSelectionModel(self, nodes_selection_model: QItemSelectionModel):
        """
        Set the selection model for the nodes.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(nodes_selection_model, QItemSelectionModel), f"got: {nodes_selection_model}"
        assert self._links_model, "Model must be set before setting the selection model!"
        assert nodes_selection_model.model() == self._links_model.nodesModel(), "Selection model must be for the same model as the graph view!"
        
        if self._nodes_selection_model:
            for signal, slot in self._nodes_selection_connections:
                signal.disconnect(slot)
            self._nodes_selection_connections = []
        
        if nodes_selection_model:
            self._nodes_selection_connections = [
                (nodes_selection_model.selectionChanged, self._on_nodes_selection_changed),
                (nodes_selection_model.currentChanged, self._on_nodes_current_changed),
            ]
            for signal, slot in self._nodes_selection_connections:
                signal.connect(slot)

        self._nodes_selection_model = nodes_selection_model
        
        scene = self.scene()
        assert scene is not None
        scene.selectionChanged.connect(self._sync_node_selection_model)

        # initialize selection state in the view to match the selection model
        if self._nodes_selection_model:
            selected = self._nodes_selection_model.selection()
            self._on_nodes_selection_changed(selected, QItemSelection())

    def nodesSelectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._nodes_selection_model
    
    def setLinksSelectionModel(self, links_selection_model: QItemSelectionModel):
        """
        Set the selection model for the _links_.
        This is used to synchronize the selection of _links_ in the graph view
        with the selection model.
        """
        assert isinstance(links_selection_model, QItemSelectionModel), f"got: {links_selection_model}"
        assert self._links_model, "Model must be set before setting the selection model!"
        assert links_selection_model.model() == self._links_model, "Selection model must be for the same model as the graph view!"
        
        if self._links_selection_model:
            for signal, slot in self._links_selection_connections:
                signal.disconnect(slot)
            self._links_selection_connections = []
        
        if links_selection_model:
            self._links_selection_connections = [
                (links_selection_model.selectionChanged, self._on_links_selection_changed),
                (links_selection_model.currentChanged, self._on_links_current_changed),
            ]
            for signal, slot in self._links_selection_connections:
                signal.connect(slot)

        self._links_selection_model = links_selection_model
        
        scene = self.scene()
        assert scene is not None
        scene.selectionChanged.connect(self._sync_link_selection_model)

        # initialize selection state in the view to match the selection model
        if self._links_selection_model:
            selected = self._links_selection_model.selection()
            self._on_links_selection_changed(selected, QItemSelection())

    def linksSelectionModel(self) -> QItemSelectionModel | None:
        return self._links_selection_model

    @Slot(QItemSelection, QItemSelection)
    def _on_nodes_selection_changed(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        assert self._nodes_selection_model, "Selection model must be set before handling selection changes!"

        if not len(selected) and not len(deselected):
            return
        
        scene = self.scene()
        assert scene is not None

        with blockingSignals(scene):           
            for index in deselected.indexes():
                if index.isValid():
                    if widget:=self._row_widget_manager.getWidget(index):
                        if widget.scene() and widget.isSelected():
                            widget.setSelected(False)
                            
            for index in selected.indexes():
                if index.isValid():
                    if widget:=self._row_widget_manager.getWidget(index):
                        if widget.scene() and not widget.isSelected():
                            widget.setSelected(True)

    @Slot(QModelIndex, QModelIndex)
    def _on_nodes_current_changed(self, current:QModelIndex, previous:QModelIndex):
        ...

    @Slot(QItemSelection, QItemSelection)
    def _on_links_selection_changed(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the _links_ selection in the graph view.
        """
        assert self._links_selection_model, "Selection model must be set before handling selection changes!"

        if not len(selected) and not len(deselected):
            return
        
        scene = self.scene()
        assert scene is not None

        with blockingSignals(scene):           
            for index in deselected.indexes():
                if index.isValid():
                    if widget:=self._link_widget_manager.getWidget(index):
                        if widget.scene() and widget.isSelected():
                            widget.setSelected(False)
                            
            for index in selected.indexes():
                if index.isValid():
                    if widget:=self._link_widget_manager.getWidget(index):
                        if widget.scene() and not widget.isSelected():
                            widget.setSelected(True)

    @Slot(QModelIndex, QModelIndex)
    def _on_links_current_changed(self, current:QModelIndex, previous:QModelIndex):
        ...

    def _sync_node_selection_model(self):
        """update selection controller from scene selection"""
        # print("Syncing selection controller from scene selection...")
        scene = self.scene()
        assert scene is not None
        if self._links_model and self._nodes_selection_model:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to indexes
            _ = map(self._row_widget_manager.getIndex, selected_widgets)
            _ = filter(lambda idx: idx is not None and idx.isValid(), _)
            selected_indexes = cast(list[QModelIndex], list(_))
            
            assert self._links_model, "Model must be set before syncing selection!"
            def selectionFromIndexes(selected_indexes:Iterable[QModelIndex]) -> QItemSelection:
                """Create a QItemSelection from a list of selected indexes."""
                item_selection = QItemSelection()
                for index in selected_indexes:
                    if index.isValid():
                        item_selection.select(index, index)
                
                return item_selection
            item_selection = selectionFromIndexes(selected_indexes)

            # perform selection on model
            self._nodes_selection_model.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(selected_indexes) > 0:
                last_selected_index = selected_indexes[-1]
                self._nodes_selection_model.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
            else:
                self._nodes_selection_model.clearSelection()
                self._nodes_selection_model.clearCurrentIndex()

    def _sync_link_selection_model(self):
        """update selection controller from scene selection"""
        # print("Syncing link selection model from scene selection...")
        scene = self.scene()
        assert scene is not None
        if self._links_model and self._links_selection_model:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to indexes
            _ = map(self._link_widget_manager.getIndex, selected_widgets)
            _ = filter(lambda idx: idx is not None and idx.isValid(), _)
            selected_indexes = cast(list[QModelIndex], list(_))
            
            assert self._links_model, "Model must be set before syncing selection!"
            def selectionFromIndexes(selected_indexes:Iterable[QModelIndex]) -> QItemSelection:
                """Create a QItemSelection from a list of selected indexes."""
                item_selection = QItemSelection()
                for index in selected_indexes:
                    if index.isValid():
                        item_selection.select(index, index)
                
                return item_selection
            item_selection = selectionFromIndexes(selected_indexes)

            # perform selection on model
            self._links_selection_model.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(selected_indexes) > 0:
                last_selected_index = selected_indexes[-1]
                self._links_selection_model.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
            else:
                self._links_selection_model.clearSelection()
                self._links_selection_model.clearCurrentIndex()

    ## Handle mouse events
    def mousePressEvent(self, event:QMouseEvent):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        # if self._linking_tool.isActive():
        #     # If we are already linking, cancel the linking operation
        #     self._linking_tool.cancelLinking()
        #     return

        # get the index at the mouse position
        pos = event.position()
        scene_pos = self.mapToScene(event.position().toPoint())

        # row interaction
        # start link
        row_index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))
        row_widget = self._row_widget_manager.getWidget(row_index)
        if row_index and self._delegate.canStartLink(row_index, row_widget, event):
            linking_direction = self._delegate.linkDirectionHint(row_index, row_widget, event)
            self._interaction_mode = "LINKING"
            self._interaction_payload = (row_index, linking_direction)  # TODO: consider renaming 'outlet' to 'forward' and 'inlet' to 'backward'
            self._draft_link = self._delegate.createLinkWidget(None, row_widget, None)
            scene = self.scene()
            assert scene is not None
            scene.addItem(self._draft_link)
        else:
            # Fallback to default behavior
            link_index = self.linkAt(QPoint(int(pos.x()), int(pos.y())))
            if link_index and link_index.isValid():
                # link interaction
                # - relink -
                link_widget = self._link_widget_manager.getWidget(link_index)
                local_pos = link_widget.mapFromScene(scene_pos)  # Ensure scene_pos is in the correct coordinate system
                tail_distance = (local_pos-link_widget.line().p1()).manhattanLength()
                head_distance = (local_pos-link_widget.line().p2()).manhattanLength()

                linking_direction = 'backward' if head_distance > tail_distance else 'forward'
                self._interaction_payload = link_index, linking_direction
                self._interaction_mode = "LINKING"
                return
            else:
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        view_pos = QPoint(int(event.position().x()), int(event.position().y()))
        scene_pos = self.mapToScene(QPoint(int(view_pos.x()), int(view_pos.y())))
        match self._interaction_mode:
            case "LINKING":
                payload_index, payload_direction = self._interaction_payload
                if payload_index.model() is self._links_model:
                    if payload_direction == "forward":
                        link_widget = self._link_widget_manager.getWidget(payload_index)
                        source_index = self._links_model.linkSource(payload_index)
                        source_widget = self._row_widget_manager.getWidget(source_index) if source_index is not None else None
                        
                        self._delegate.moveLinkWidget(link_widget, source_widget, scene_pos)
                    elif payload_direction == "backward":
                        link_widget = self._link_widget_manager.getWidget(payload_index)
                        target_index = self._links_model.linkTarget(payload_index)
                        target_widget = self._row_widget_manager.getWidget(target_index) if target_index is not None else None

                        self._delegate.moveLinkWidget(link_widget, scene_pos, target_widget)

                elif payload_index.model() is self._links_model.nodesModel():
                    if payload_direction == "forward":
                        end_index = self.rowAt(view_pos)  # Ensure the index is updated
                        end_widget = self._row_widget_manager.getWidget(end_index) #TODO: consider using invalid QModelIndex instead of None?
                        
                        start_widget = self._row_widget_manager.getWidget(payload_index)
                        if end_index and end_index.isValid() and self._delegate.canAcceptLink(payload_index, end_index, start_widget, end_widget, event): # TODO: add option for snap behaviour
                            self._delegate.moveLinkWidget(self._draft_link, start_widget, end_widget)
                        else:
                            self._delegate.moveLinkWidget(self._draft_link, start_widget, scene_pos)

                    elif payload_direction == "backward":
                        end_index = self.rowAt(view_pos)  # Ensure the index is updated
                        end_widget = self._row_widget_manager.getWidget(end_index) #TODO: consider using invalid QModelIndex instead of None?
                        
                        start_widget = self._row_widget_manager.getWidget(payload_index)
                        if end_index and end_index.isValid() and self._delegate.canAcceptLink(end_index, payload_index, end_widget, start_widget, event): # TODO: add option for snap behaviour
                            self._delegate.moveLinkWidget(self._draft_link, end_widget, start_widget)
                        else:
                            self._delegate.moveLinkWidget(self._draft_link, scene_pos, start_widget)


            case _:
                super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._interaction_mode != "LINKING":
            super().mouseReleaseEvent(event)
            return

        assert self._links_model, "Model must be set before handling mouse release!"

        def reset_linking_state() -> None: #TODO: consider removing/refactoring these functions
            self._interaction_mode = None
            self._interaction_payload = None

        def destroy_draft_link(start_widget, end_widget) -> None:  #TODO: consider removing/refactoring these functions
            if self._draft_link is not None:
                if start_widget is None and end_widget is None:
                    if scene := self._draft_link.scene():
                        scene.removeItem(self._draft_link)
                else:
                    self._delegate.destroyLinkWidget(self._draft_link, None, start_widget, end_widget)
                    scene = self.scene()
                    assert scene is not None
                    scene.removeItem(self._draft_link)
                self._draft_link = None

        if not self._interaction_payload:
            reset_linking_state()
            return

        payload_index, linking_direction = self._interaction_payload
        view_pos = QPoint(int(event.position().x()), int(event.position().y()))
        drop_index = self.rowAt(view_pos)

        if payload_index.model() is self._links_model:
            if linking_direction == "forward":
                link_index = payload_index
                if not link_index or not link_index.isValid():
                    reset_linking_state()
                    return

                row = link_index.row()
                source_index = self._links_model.linkSource(link_index)
                prev_target_index = self._links_model.linkTarget(link_index)
                link_widget = self._link_widget_manager.getWidget(link_index)
                source_widget = self._row_widget_manager.getWidget(source_index)
                prev_target_widget = self._row_widget_manager.getWidget(prev_target_index)

                if not link_widget:
                    reset_linking_state()
                    return

                if not drop_index or not drop_index.isValid():
                    self._links_model.remove_link(row)
                    reset_linking_state()
                    return

                new_target_index = drop_index
                if new_target_index == prev_target_index:
                    self._delegate.moveLinkWidget(link_widget, source_widget, prev_target_widget)
                    reset_linking_state()
                    return

                new_target_widget = self._row_widget_manager.getWidget(new_target_index)
                if self._delegate.canAcceptLink(source_index, new_target_index, source_widget, new_target_widget, event):
                    self._links_model.set_link(row, source_index, new_target_index)
                    self._delegate.moveLinkWidget(link_widget, source_widget, new_target_widget)
                else:
                    self._delegate.moveLinkWidget(link_widget, source_widget, prev_target_widget)
                reset_linking_state()
                return
            
            elif linking_direction == "backward":
                link_index = payload_index
                if not link_index or not link_index.isValid():
                    reset_linking_state()
                    return

                row = link_index.row()
                prev_source_index = self._links_model.linkSource(link_index)
                target_index = self._links_model.linkTarget(link_index)
                link_widget = self._link_widget_manager.getWidget(link_index)
                prev_source_widget = self._row_widget_manager.getWidget(prev_source_index)
                target_widget = self._row_widget_manager.getWidget(target_index)

                if not link_widget:
                    reset_linking_state()
                    return

                if not drop_index or not drop_index.isValid():
                    self._links_model.remove_link(row)
                    reset_linking_state()
                    return

                new_source_index = drop_index
                if new_source_index == prev_source_index:
                    self._delegate.moveLinkWidget(link_widget, prev_source_widget, target_widget)
                    reset_linking_state()
                    return

                new_source_widget = self._row_widget_manager.getWidget(new_source_index)
                if self._delegate.canAcceptLink(new_source_index, target_index, new_source_widget, target_widget, event):
                    self._links_model.set_link(row, new_source_index, target_index)
                    self._delegate.moveLinkWidget(link_widget, new_source_widget, target_widget)
                else:
                    self._delegate.moveLinkWidget(link_widget, prev_source_widget, target_widget)
                reset_linking_state()
                return
            else:
                reset_linking_state()
                return
            
        elif payload_index.model() is self._links_model.nodesModel():
            if drop_index is None or not drop_index.isValid():
                # create and link new node at mousepos
                nodes_model = self._links_model.nodesModel()

                start_index = payload_index
                start_widget = self._row_widget_manager.getWidget(start_index)
                # End draft interaction first; the final link widget is created via model insertion.
                reset_linking_state()
                destroy_draft_link(start_widget, None)

                drop_scene_pos = self.mapToScene(QPoint(int(event.position().x()), int(event.position().y())))
                if self._create_new_node_at_position(drop_scene_pos):
                    new_node_index = nodes_model.index(nodes_model.rowCount()-1, 0, QModelIndex())

                    if linking_direction == "forward":
                        self._links_model.add_link(start_index, new_node_index)
                    elif linking_direction == "backward":
                        self._links_model.add_link(new_node_index, start_index)
                return

            if linking_direction == "forward":
                start_index = payload_index
                start_widget = self._row_widget_manager.getWidget(start_index)
                end_index = drop_index if drop_index and drop_index.isValid() else None
                end_widget = self._row_widget_manager.getWidget(end_index) if end_index else None

                can_link = bool(
                    end_index
                    and self._delegate.canAcceptLink(start_index, end_index, start_widget, end_widget, event)
                )
                destroy_draft_link(start_widget, end_widget)
                reset_linking_state()
                if can_link:
                    self._links_model.add_link(start_index, end_index)
                return
            elif linking_direction == "backward":
                end_index = payload_index
                end_widget = self._row_widget_manager.getWidget(end_index)
                start_index = drop_index if drop_index and drop_index.isValid() else None
                start_widget = self._row_widget_manager.getWidget(start_index) if start_index else None

                can_link = bool(
                    start_index
                    and self._delegate.canAcceptLink(start_index, end_index, start_widget, end_widget, event)
                )
                destroy_draft_link(start_widget, end_widget)
                reset_linking_state()
                if can_link:
                    self._links_model.add_link(start_index, end_index)
                return
            else:
                reset_linking_state()
                return
        else:
            reset_linking_state()
            return

    def mouseDoubleClickEvent(self, event):
        if self._links_model is None:
            super().mouseDoubleClickEvent(event)
            return
        
        pos = event.position()
        cell_index = self.cellAt(QPoint(int(pos.x()), int(pos.y())))
        nodes_model = self._links_model.nodesModel()

        if cell_index and nodes_model.flags(cell_index) & Qt.ItemFlag.ItemIsEditable:
            # start editing the cell
            self._close_active_editor(commit=False)
            option = QStyleOptionViewItem()
            option.font = self.font()
            option.palette = self.palette()
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            cell_widget = self._cell_widget_manager.getWidget(cell_index)
            if not cell_widget:
                super().mouseDoubleClickEvent(event)
                return
            scene_rect = cell_widget.mapToScene(cell_widget.boundingRect()).boundingRect()
            option.rect = self.mapFromScene(scene_rect).boundingRect()
            option.widget = self.viewport()
            editor = self._delegate.createEditor(self.viewport(), option, cell_index)
            editor.setGeometry(option.rect)
            editor.setParent(self.viewport())
            editor.raise_()
            editor.installEventFilter(self)
            self._active_editor = editor
            self._active_editor_index = QPersistentModelIndex(cell_index)
            self._delegate.setEditorData(editor, cell_index)
            if isinstance(editor, QLineEdit):
                editor.textEdited.connect(self._commit_active_editor)
            editor.setFocus()
            editor.show()
            return
        else:
            scene_pos = self.mapToScene(QPoint(int(event.position().x()), int(event.position().y())))
            self._create_new_node_at_position(scene_pos)

            return
        super().mouseDoubleClickEvent(event)

    def _create_new_node_at_position(self, scene_pos: QPointF) -> bool:
        # create new node at position
        if self._links_model is None:
            return False
        
        nodes_model = self._links_model.nodesModel()
        new_node_row = nodes_model.rowCount()
        if nodes_model.insertRows(new_node_row, 1, QModelIndex()):
            new_node_index = nodes_model.index(new_node_row, 0, QModelIndex())
            new_node_widget = self._row_widget_manager.getWidget(new_node_index)
            if new_node_widget is not None:
                center = new_node_widget.boundingRect().center()
                print(f"Placing new node at {scene_pos}, center offset {center}")
                new_node_widget.setPos(scene_pos-center)
            return True
        return False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._active_editor:
            if event.type() == QEvent.Type.FocusOut:
                self._close_active_editor(commit=True)
                return False
            if event.type() == QEvent.Type.KeyPress:
                key_event = cast(QKeyEvent, event)
                if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._close_active_editor(commit=True)
                    return True
                if key_event.key() == Qt.Key.Key_Escape:
                    self._close_active_editor(commit=False)
                    return True
        return super().eventFilter(watched, event)

    def _close_active_editor(self, commit: bool) -> None:
        if self._active_editor is None:
            return
        editor = self._active_editor
        editor_index = self._active_editor_index
        self._active_editor = None
        self._active_editor_index = None
        editor.removeEventFilter(self)
        if commit:
            self._commit_editor(editor, editor_index)
        editor.deleteLater()

    def _commit_active_editor(self, *_args) -> None:
        self._commit_editor(self._active_editor, self._active_editor_index)

    def _commit_editor(self, editor: QWidget | None, editor_index: QPersistentModelIndex | None) -> None:
        if editor is None or editor_index is None or not editor_index.isValid():
            return
        self._delegate.setModelData(editor, QModelIndex(editor_index))

    def layout_nodes_graphviz(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        layer_spacing: float = 70.0,
        node_spacing: float = 120.0,
    ):
        # winget install Graphviz.Graphviz
        """Layout nodes with Graphviz dot (via pydot); fallback to topo spacing."""
        if self._links_model is None:
            return
        nodes_model = self._links_model.nodesModel()
        if nodes_model is None:
            return None
        
        import pydot

        dot = pydot.Dot(graph_type="digraph", rankdir="TB")
        for node_row in range(nodes_model.rowCount()):
            node_name = f"N{node_row}"
            node_index = nodes_model.index(node_row, 0)
            inlet_count = nodes_model.rowCount(node_index)

            ports = "|".join(f"<in{i}> in{i}" for i in range(inlet_count))
            label = f"{{{node_name}|{{{ports}}}}}"

            dot.add_node(pydot.Node(node_name, shape="record", label=label))

        for link_row in range(self._links_model.rowCount()):
            link_index = self._links_model.index(link_row, 0)
            src_outlet = self._links_model.linkSource(link_index)
            src_node = src_outlet
            while src_node.parent().isValid():
                src_node = src_node.parent()
            dst_inlet = self._links_model.linkTarget(link_index)
            dst_node = dst_inlet
            while dst_node.parent().isValid():
                dst_node = dst_node.parent()

            src = f"N{src_node.row()}"
            dst = f"N{dst_node.row()}"

            dot.add_edge(pydot.Edge(src, f"{dst}:in{dst_inlet.row()}"))

        dot_graph = dot.create_dot(prog="dot")

        layout_graph = pydot.graph_from_dot_data(dot.create_dot().decode())[0]

        for node in layout_graph.get_nodes():
            name = node.get_name().strip('"')
            pos = node.get_pos()
            print(name, pos)

    def layout_nodes(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        layer_spacing: float = 70.0,
        node_spacing: float = 120.0,
    ):
        """Layout nodes with Graphviz dot (via pydot); fallback to topo spacing."""
        try:
            import networkx as nx
        except ImportError:
            warnings.warn("NetworkX is not installed. Please install it to use the layout feature.")
            return

        if not self._links_model:
            return nx.DiGraph()

        G = self._links_model.toNetworkX()

        # Preferred: Graphviz dot via networkx + pydot.
        try:
            from networkx.drawing.nx_pydot import graphviz_layout

            pos = graphviz_layout(G, prog="dot")

            # Normalize dot coords into scene spacing units.
            xs = [float(x) for x, _ in pos.values()]
            ys = [float(y) for _, y in pos.values()]
            min_x, max_x = (min(xs), max(xs)) if xs else (0.0, 0.0)
            min_y, max_y = (min(ys), max(ys)) if ys else (0.0, 0.0)
            span_x = max(max_x - min_x, 1.0)
            span_y = max(max_y - min_y, 1.0)

            # Estimate grid extents from topo layers.
            layers = [list(layer) for layer in nx.topological_generations(G)]
            layer_count = max(len(layers), 1)
            max_nodes_in_layer = max((len(layer) for layer in layers), default=1)

            for node, (x, y) in pos.items():
                node_widget = self._row_widget_manager.getWidget(node)
                if not node_widget:
                    continue

                norm_x = (float(x) - min_x) / span_x
                norm_y = (float(y) - min_y) / span_y

                px = norm_x * max(1, max_nodes_in_layer - 1) * float(node_spacing)
                py = (1.0 - norm_y) * max(1, layer_count - 1) * float(layer_spacing)

                if orientation == Qt.Orientation.Vertical:
                    node_widget.setPos(px, py)
                else:
                    node_widget.setPos(py, px)
            return
        except ImportError:
            warnings.warn("pydot/graphviz is not available, falling back to simple layered layout.")
        except Exception as e:
            warnings.warn(f"pydot/graphviz layout failed ({e}), falling back to simple layered layout.")

        # Fallback: simple layers from DAG topology.
        try:
            layers = [list(layer) for layer in nx.topological_generations(G)]
        except nx.NetworkXUnfeasible:
            warnings.warn("Graph contains cycles; cannot use topological generations.")
            return

        for layer_idx, layer_nodes in enumerate(layers):
            # stable order inside layer
            ordered = sorted(layer_nodes, key=lambda idx: idx.row())
            center_offset = (len(ordered) - 1) * 0.5 * node_spacing

            for i, node_index in enumerate(ordered):
                node_widget = self._row_widget_manager.getWidget(node_index)
                if not node_widget:
                    continue

                primary = layer_idx * layer_spacing
                secondary = i * node_spacing - center_offset

                if orientation == Qt.Orientation.Vertical:
                    node_widget.setPos(secondary, primary)   # x, y
                else:
                    node_widget.setPos(primary, secondary)   # x, y
                    
    def isColumnHidden(self, column:int) -> bool:
        """Check if a column is hidden."""
        return self._is_column_hidden.get(column, False)
    
    def setColumnHidden(self, column:int, hidden:bool):
        """Called when a column is hidden or shown. Override this method to implement custom logic."""
        self._is_column_hidden[column] = hidden

        # update cells visibility in the column
        if self._links_model is None:
            return
        
        nodes_model = self._links_model.nodesModel()
        if nodes_model is None:
            return
        
        for row in range(self._links_model.nodesModel().rowCount()):
            cell_index = self._links_model.nodesModel().index(row, column)
            row_index = cell_index.siblingAtColumn(0)
            row_widget = self._row_widget_manager.getWidget(row_index)
            if not row_widget:
                continue
            row_widget.prepareGeometryChange()
            
            if cell_widget := self._cell_widget_manager.getWidget(cell_index):
                cell_widget.setVisible(not hidden)
            row_widget.update_layout()
            
            
         
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

