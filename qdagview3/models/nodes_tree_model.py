from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt


@dataclass
class StandardNodesItem:
    values: List[str]
    parent: Optional["StandardNodesItem"] = None
    children: List["StandardNodesItem"] = field(default_factory=list)

    def child(self, row: int) -> Optional["StandardNodesItem"]:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def column_count(self) -> int:
        return len(self.values)

    def row(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.children.index(self)

    def insert_child(self, row: int, item: "StandardNodesItem") -> None:
        item.parent = self
        self.children.insert(row, item)

    def remove_child(self, row: int) -> bool:
        if 0 <= row < len(self.children):
            child = self.children.pop(row)
            child.parent = None
            return True
        return False

    def insert_column(self, column: int, default_value: str = "") -> None:
        self.values.insert(column, default_value)
        for child in self.children:
            child.insert_column(column, default_value)

    def remove_column(self, column: int) -> None:
        if 0 <= column < len(self.values):
            self.values.pop(column)
        for child in self.children:
            child.remove_column(column)


class NodesTreeModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._headers: List[str] = ["Column 1"]
        self._root = StandardNodesItem(values=["Root"])

    def itemFromIndex(self, index: QModelIndex) -> StandardNodesItem:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self._root

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.itemFromIndex(parent)
        child_item = parent_item.child(row)
        if child_item is None:
            return QModelIndex()

        return self.createIndex(row, column, child_item)

    def parent(self, index: QModelIndex) -> QModelIndex: #type: ignore[override]
        if not index.isValid():
            return QModelIndex()

        child_item = self.itemFromIndex(index)
        parent_item = child_item.parent

        if parent_item is None or parent_item is self._root:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        parent_item = self.itemFromIndex(parent)
        return parent_item.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            item = self.itemFromIndex(parent)
            return item.column_count()
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        item = self.itemFromIndex(index)
        if 0 <= index.column() < len(item.values):
            return item.values[index.column()]
        return ""

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False

        item = self.itemFromIndex(index)
        if not (0 <= index.column() < len(item.values)):
            return False

        item.values[index.column()] = str(value)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

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
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.EditRole:
            return False
        if not (0 <= section < len(self._headers)):
            return False

        self._headers[section, role] = str(value)
        self.headerDataChanged.emit(orientation, section, section)
        return True

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)
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

        parent_item = self.itemFromIndex(parent)
        if row < 0 or row + count > parent_item.child_count():
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        for _ in range(count):
            parent_item.remove_child(row)
        self.endRemoveRows()
        return True

    def insertColumns(self, column: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if parent.isValid() or count <= 0:
            return False
        if column < 0 or column > len(self._headers):
            return False

        self.beginInsertColumns(QModelIndex(), column, column + count - 1)
        for offset in range(count):
            self._headers.insert(column + offset, f"Column {column + offset + 1}")
            self._root.insert_column(column + offset, "")
        self.endInsertColumns()
        return True

    def removeColumns(self, column: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if parent.isValid() or count <= 0:
            return False
        if column < 0 or column + count > len(self._headers):
            return False
        if len(self._headers) - count < 1:
            return False

        self.beginRemoveColumns(QModelIndex(), column, column + count - 1)
        for _ in range(count):
            self._headers.pop(column)
            self._root.remove_column(column)
        self.endRemoveColumns()
        return True


