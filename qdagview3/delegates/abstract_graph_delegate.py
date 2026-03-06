from abc import ABC, abstractmethod
from typing import Literal, Type

from qtpy.QtCore import (
    QObject, 
    QModelIndex, 
    QAbstractItemModel, 
    QPersistentModelIndex,
    Signal,
    Qt
)
from qtpy.QtWidgets import (
    QGraphicsScene, 
    QGraphicsItem, 
    QStyleOptionViewItem,
    QWidget, QLineEdit
)
from qtpy.QtCore import (
    QEvent, 
    QPointF
)

from abc import ABC, abstractmethod, ABCMeta
from qdagview3.views.widgets.fitting_line_edit import FittingLineEdit

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
    def setRowWidgetData(self, row_widget:RowWidgetT, index:QModelIndex):
        """Set the data for the row widget. This is called when a vertical header is updated of the nodes model."""
        ...

    @abstractmethod
    def setRowModelData(self, row_widget:RowWidgetT, index:QModelIndex):
        """Set the data for the vertical header. This is called when a row widget is edited."""
        ...

    @abstractmethod
    def setCellWidgetData(self, cell:CellWidgetT, index:QModelIndex):
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
        
    def createEditor(self, parent_widget:'QDAGView', option:QStyleOptionViewItem, index:QModelIndex) -> QWidget:
        """Create an editor for the given index. This is called when a cell widget is double-clicked."""
        return FittingLineEdit(parent_widget)
    
    def setEditorData(self, editor: QWidget, index: QModelIndex):
        """Set the data for the editor. This is called when an editor is created."""
        if isinstance(editor, QLineEdit):
            value = index.data(Qt.ItemDataRole.EditRole)
            if value is None:
                value = index.data(Qt.ItemDataRole.DisplayRole)
            editor.setText("" if value is None else str(value))
            editor.selectAll()

    def setModelData(self, editor: QWidget, index: QModelIndex):
        """Set the data for the model. This is called when an editor is closed."""
        if not index.isValid():
            return
        model = index.model()
        if model is None:
            return
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
