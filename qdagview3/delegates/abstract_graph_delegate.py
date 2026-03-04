from abc import ABC, abstractmethod
from typing import Literal, Type

from qtpy.QtCore import QObject, QModelIndex, QAbstractItemModel, QPersistentModelIndex
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QGraphicsScene, QGraphicsItem
from qtpy.QtCore import QEvent, QPointF

from abc import ABC, abstractmethod, ABCMeta

# generic types definitions for type hinting
RowWidgetT =  QGraphicsItem
CellWidgetT = QGraphicsItem
LinkWidgetT = QGraphicsItem

# 1. Create a combined metaclass
class QABCMeta(type(QObject), ABCMeta):
    pass


class AbstractGraphDelegate(QObject, ABC, metaclass=QABCMeta):
    portPositionChanged = Signal(object)

    ## Root widgets
    @abstractmethod
    def createRowWidget(self, parent_widget: RowWidgetT|None, index:QModelIndex) -> RowWidgetT:
        ...

    @abstractmethod
    def destroyRowWidget(self, parent_widget: QGraphicsScene, widget: RowWidgetT)->bool:
        ...
    
    @abstractmethod
    def createCellWidget(self, parent_widget: RowWidgetT, index: QModelIndex) -> CellWidgetT:
        ...
    
    @abstractmethod
    def destroyCellWidget(self, parent_widget: RowWidgetT, widget: CellWidgetT)->bool:
        ...

    @abstractmethod
    def createLinkWidget(self, link_index: QModelIndex|None, source_widget:RowWidgetT|None, target_widget:RowWidgetT|None, ) -> LinkWidgetT:
        ...
    
    @abstractmethod
    def moveLinkWidget(self, link_widget: LinkWidgetT, start_widget: QGraphicsItem|QPointF, end_widget: QGraphicsItem|QPointF):
        ...
    
    @abstractmethod
    def destroyLinkWidget(self, link_widget: LinkWidgetT, source_widget:RowWidgetT|None, target_widget:RowWidgetT|None)->bool:
        ...

    @abstractmethod
    def setRowEditorData(self, row_widget:RowWidgetT, index:QModelIndex):
        """Set the data for the row widget. This is called when a vertical header is updated of the nodes model."""
        ...

    @abstractmethod
    def setRowModelData(self, row_widget:RowWidgetT, index:QModelIndex):
        """Set the data for the vertical header. This is called when a row widget is edited."""
        ...

    @abstractmethod
    def setCellEditorData(self, cell:CellWidgetT, index:QModelIndex):
        ...
    
    @abstractmethod
    def setCellModelData(self, cell:CellWidgetT, index:QModelIndex):
        ...

    @abstractmethod
    def canStartLink(self, start_index: QModelIndex, start_widget:RowWidgetT|None=None, event:QEvent|None=None) -> bool:
        return True
    
    def linkDirectionHint(self, start_index: QModelIndex, start_widget:RowWidgetT|None=None, event:QEvent|None=None) -> Literal["forward", "backward", None]:
        """This method is called during the dragging of a new link, 
        and can be used to provide hints about the link direction."""
        return "Forward"
    
    @abstractmethod
    def canAcceptLink(self, start_index: QModelIndex, end_index: QModelIndex, start_widget:RowWidgetT|None=None, end_widget:RowWidgetT|None=None, event:QEvent|None=None) -> bool:
        return True
        