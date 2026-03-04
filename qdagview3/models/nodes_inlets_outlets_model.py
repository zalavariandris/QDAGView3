from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt


@dataclass
class RootData:
    nodes: List[NodeData] = field(default_factory=list)

@dataclass
class InletData:
    name: str
    node: NodeData

@dataclass
class OutletData:
    name: str
    node: NodeData

@dataclass
class NodeData:
    name: str
    graph: RootData
    inlets: List[InletData] = field(default_factory=list)
    outlets: List[OutletData] = field(default_factory=list)


class StandardNodesModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._headers: List[str] = ["expression"]
        self._root = RootData()

    def _item_from_index(self, index: QModelIndex) -> StandardNodesItem:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self._root

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self._item_from_index(parent)
        child_item = parent_item.child(row)
        if child_item is None:
            return QModelIndex()

        return self.createIndex(row, column, child_item)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item = self._item_from_index(index)
        match child_item:
            case NodeData():
                return None
            
            case InletData():
                inlet = child_item
                node = child_item.node
                row = node.inlets.index(inlet)
                return self.createIndex(row, 0, node)

            case OutletData():
                outlet = child_item
                node = child_item.node
                row = node.outlets.index(outlet)
                return self.createIndex(row, 0, node)

            case _:
                raise TypeError(f"Unexpected item type: {child_item}")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self._item_from_index(parent)
        match item:
            case NodeData():
                node = item
                return len(node.inlets) + len(node.outlets)
            
            case InletData():
                return 0

            case OutletData():
                return 0

            case _:
                raise TypeError(f"Unexpected item type: {parent}")

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self._item_from_index(parent)
        match item:
            case NodeData():
                return 1
            
            case InletData():
                return 1

            case OutletData():
                return 1

            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        
        if index.column() != 0:
            return None

        item = self._item_from_index(index)
        match item:
            case NodeData():
                node = item
                return node.name
            case InletData():
                inlet = item
                return inlet.name
            case OutletData():
                outlet = item
                return outlet.name
            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return False
        
        if index.column() != 0:
            return False

        item = self._item_from_index(index)
        match item:
            case NodeData():
                node = item
                node.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            
            case InletData():
                inlet = item
                inlet.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            
            case OutletData():
                outlet = item
                outlet.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            
            case _:
                return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role in (Qt.DisplayRole, Qt.EditRole):
            if 0 <= section < len(self._headers):
                return self._headers[section]
            
        if orientation == Qt.Vertical and role in (Qt.DisplayRole, Qt.EditRole):
            return f"{section}"
        return None

    def setHeaderData(
        self,
        section: int,
        orientation: Qt.Orientation,
        value,
        role: int = Qt.EditRole,
    ) -> bool:
        if orientation != Qt.Horizontal or role != Qt.EditRole:
            return False
        if not (0 <= section < len(self._headers)):
            return False

        self._headers[section] = str(value)
        self.headerDataChanged.emit(orientation, section, section)
        return True

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self._item_from_index(parent)
        if row < 0 or row > parent_item.child_count():
            return False

        self.beginInsertRows(parent, row, row + count - 1)
        for offset in range(count):
            item_row = row + offset + 1
            new_values = [f"Item {item_row}"] + ["" for _ in range(self.columnCount(parent) - 1)]
            parent_item.insert_child(row + offset, StandardNodesItem(values=new_values, parent=parent_item))
        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self._item_from_index(parent)
        if row < 0 or row + count > parent_item.child_count():
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        for _ in range(count):
            parent_item.remove_child(row)
        self.endRemoveRows()
        return True
