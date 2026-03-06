from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from bidict import bidict
import warnings
from typing import List

class PersistentIndexWidgetManager:
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        # self._widgets: bidict[QPersistentModelIndex, QGraphicsItem] = bidict()
        self._widget_to_index: dict[QGraphicsItem, QPersistentModelIndex] = dict()
        self._index_to_widget: dict[QPersistentModelIndex, QGraphicsItem] = dict()

    def insertWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        persistent_idx = QPersistentModelIndex(index)
        assert persistent_idx.isValid()
        self._index_to_widget[persistent_idx] = widget
        self._widget_to_index[widget] = persistent_idx

    def removeWidget(self, index:QModelIndex|QPersistentModelIndex):
        """Remove a widget from the manager."""
        persistent_idx = QPersistentModelIndex(index)
        widget = self._index_to_widget.pop(persistent_idx, None)
        if widget:
            self._widget_to_index.pop(widget, None)

    def getWidget(self, index: QModelIndex|None) -> QGraphicsItem|None:
        if index is None:
            warnings.warn("Index is None")
            return None
        if not index.isValid():
            warnings.warn(f"Index is invalid: {index}")
            return None
        
        # convert to persistent index
        persistent_idx = QPersistentModelIndex(index)
        return self._index_to_widget.get(persistent_idx, None)   
    
    def getIndex(self, widget:QGraphicsItem) -> QModelIndex|None:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        persistent_idx = self._widget_to_index.get(widget, None)
        return QModelIndex(persistent_idx) if persistent_idx else None

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widget_to_index.keys())
    
    def clear(self):
        self._widget_to_index.clear()
        self._index_to_widget.clear()