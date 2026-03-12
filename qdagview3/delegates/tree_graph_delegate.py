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
from qdagview3.delegates.abstract_graph_delegate import AbstractGraphDelegate

class TreeGraphDelegate(AbstractGraphDelegate):
    def createRowWidget(self, parent_widget: RowWidget|None, index:QModelIndex) -> RowWidget:
        if not isinstance(parent_widget, (RowWidget, type(None))):
            raise TypeError("Parent widget must be a RowWidget or None")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        widget = RowWidget()
        def onScenePositionChanged(pos, idx=QPersistentModelIndex(index)):
            print(f"Scene position of port widget for index {idx} {idx.data(Qt.ItemDataRole.DisplayRole)} changed to {pos}")
            self.portPositionChanged.emit(QModelIndex(idx))
        widget.scenePositionChanged.connect(onScenePositionChanged)
        widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        match parent_widget:
            case None:
                widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

            case RowWidget():
                parent_widget.insertChild(index.column(), widget)

            case _:
                raise TypeError("Parent widget must be a RowWidget or None")
        
        widget.title_widget.setText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
        return widget

    def destroyRowWidget(self, parent_widget: RowWidget|None, widget: RowWidget, index:QModelIndex)->bool:
        if not isinstance(parent_widget, (RowWidget, type(None))):
            raise TypeError("Parent widget must be a RowWidget or None")
        
        match parent_widget:
            case None:
                ...
            case RowWidget():
                parent_widget.removeChild(widget)
                widget.deleteLater()  # Schedule widget for deletion - this automatically disconnects all signals
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
    
    def destroyCellWidget(self, parent_widget: RowWidget, widget: CellWidget, index: QModelIndex)->bool:
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
        return link_widget
    
    def moveLinkWidget(self, link_index:QModelIndex, link_widget: LinkWidget, start_widget: QGraphicsItem|QPointF, end_widget: QGraphicsItem|QPointF):
        if not isinstance(link_widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
        
        print(f"Moving link widget between {start_widget} and {end_widget}")
        
        line = QLineF(makeLineBetweenShapes(start_widget, end_widget))
        link_widget.setLine(line)
    
    def destroyLinkWidget(self, link_widget: LinkWidget, index:QModelIndex|None, source_widget:RowWidget|None, target_widget:RowWidget|None)->bool:
        if not isinstance(source_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"source_widget must be a QGraphicsItem or None, got {type(source_widget)} instead")
        if not isinstance(target_widget, (QGraphicsItem, type(None))):
            raise TypeError(f"target_widget must be a QGraphicsItem or None, got {type(target_widget)} instead")
        if not isinstance(link_widget, LinkWidget):
            raise TypeError(f"Widget must be a LinkWidget, got {type(link_widget)} instead")
        
        link_widget.setParentItem(None)  # Remove from any parent item
        scene = source_widget.scene() if source_widget else target_widget.scene()
        # Schedule widget for deletion to prevent memory leaks TODO:
        return True

    def setRowWidgetData(self, row_widget: RowWidget, index: QModelIndex):
        print(f"Setting row editor data for index {index}, display role: {index.data(Qt.ItemDataRole.DisplayRole)}")
        row_widget.title_widget.setText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")

    def setRowModelData(self, row_widget: RowWidget, index: QModelIndex):
        model = index.model()
        model.setData(index, row_widget.title_widget._text, Qt.ItemDataRole.EditRole)

    def setCellWidgetData(self, cell:CellWidget, index:QModelIndex):
        print(f"Setting cell editor data for index {index}, display role: {index.data(Qt.ItemDataRole.DisplayRole)}")
        cell.setText(f"{index.data(Qt.ItemDataRole.DisplayRole)}")
    
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
