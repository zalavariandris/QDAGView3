from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, QPersistentModelIndex, Qt


@dataclass(slots=True)
class Link:
    source: QPersistentModelIndex
    target: QPersistentModelIndex


class LinkModel(QAbstractItemModel):
    """Flat 2-column model storing links between source-model rows.

    Column 0 stores the source row index (persisted as QPersistentModelIndex).
    Column 1 stores the target row index (persisted as QPersistentModelIndex).
    """

    SourceIndexRole = int(Qt.UserRole) + 1
    TargetIndexRole = int(Qt.UserRole) + 2

    def __init__(self, nodes_model: QAbstractItemModel, parent=None) -> None:
        super().__init__(parent)
        self._headers = ("Source", "Target")
        self._links: list[Link] = []
        self._nodes_model: QAbstractItemModel = nodes_model
        self._connect_nodes_model(nodes_model)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() or not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex) -> QModelIndex:
        del child
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._links)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        del parent
        return 2

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if not (0 <= index.row() < len(self._links)):
            return None

        link = self._links[index.row()]
        stored = link.source if index.column() == 0 else link.target

        if role == Qt.DisplayRole:
            return self._display_text(stored)
        if role == Qt.EditRole:
            return stored
        if role == self.SourceIndexRole and index.column() == 0:
            return stored
        if role == self.TargetIndexRole and index.column() == 1:
            return stored

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        if 0 <= section < len(self._headers):
            return self._headers[section]
        return None

    def nodesModel(self) -> QAbstractItemModel:
        return self._nodes_model

    def setNodesModel(self, nodes_model: QAbstractItemModel) -> None:
        if self._nodes_model is nodes_model:
            return

        if self._nodes_model is not None:
            self._disconnect_nodes_model(self._nodes_model)

        self._nodes_model = nodes_model
        self.clear_links()

        if self._nodes_model is not None:
            self._connect_nodes_model(self._nodes_model)

    def add_link(self, source: QModelIndex, target: QModelIndex) -> int:
        """Append a link and return its row index.

        Both source and target are normalized to column 0 before persisting.
        """
        source_col0 = self._normalize_to_column0(source)
        target_col0 = self._normalize_to_column0(target)
        if not self._is_valid_node_index(source_col0) or not self._is_valid_node_index(target_col0):
            return -1

        row = len(self._links)
        self.beginInsertRows(QModelIndex(), row, row)
        self._links.append(
            Link(
                source=QPersistentModelIndex(source_col0),
                target=QPersistentModelIndex(target_col0),
            )
        )
        self.endInsertRows()
        return row

    def set_link(self, row: int, source: QModelIndex, target: QModelIndex) -> bool:
        if not (0 <= row < len(self._links)):
            return False

        source_col0 = self._normalize_to_column0(source)
        target_col0 = self._normalize_to_column0(target)
        if not self._is_valid_node_index(source_col0) or not self._is_valid_node_index(target_col0):
            return False

        self._links[row] = Link(
            source=QPersistentModelIndex(source_col0),
            target=QPersistentModelIndex(target_col0),
        )
        left = self.index(row, 0)
        right = self.index(row, 1)
        self.dataChanged.emit(
            left,
            right,
            [Qt.DisplayRole, Qt.EditRole, self.SourceIndexRole, self.TargetIndexRole],
        )
        return True

    def remove_link(self, row: int) -> bool:
        if not (0 <= row < len(self._links)):
            return False

        self.beginRemoveRows(QModelIndex(), row, row)
        self._links.pop(row)
        self.endRemoveRows()
        return True

    def remove_invalid_links(self) -> int:
        """Remove links whose source or target index is no longer valid."""
        invalid_rows = [
            row
            for row, link in enumerate(self._links)
            if not link.source.isValid() or not link.target.isValid()
        ]
        for row in reversed(invalid_rows):
            self.remove_link(row)
        return len(invalid_rows)

    def clear_links(self) -> None:
        if not self._links:
            return

        self.beginResetModel()
        self._links.clear()
        self.endResetModel()

    def link_at(self, row: int) -> Optional[tuple[QPersistentModelIndex, QPersistentModelIndex]]:
        if not (0 <= row < len(self._links)):
            return None
        link = self._links[row]
        return link.source, link.target

    def _connect_nodes_model(self, model: QAbstractItemModel) -> None:
        model.rowsRemoved.connect(self._on_nodes_model_changed)
        model.modelReset.connect(self._on_nodes_model_changed)
        model.layoutChanged.connect(self._on_nodes_model_changed)
        model.destroyed.connect(self._on_nodes_model_destroyed)

    def _disconnect_nodes_model(self, model: QAbstractItemModel) -> None:
        self._safe_disconnect(model.rowsRemoved, self._on_nodes_model_changed)
        self._safe_disconnect(model.modelReset, self._on_nodes_model_changed)
        self._safe_disconnect(model.layoutChanged, self._on_nodes_model_changed)
        self._safe_disconnect(model.destroyed, self._on_nodes_model_destroyed)

    @staticmethod
    def _safe_disconnect(signal, slot) -> None:
        try:
            signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass

    def _on_nodes_model_changed(self, *args) -> None:
        del args
        self.remove_invalid_links()

    def _on_nodes_model_destroyed(self, obj: QObject) -> None:
        del obj
        self._nodes_model = None
        self.clear_links()

    def _is_valid_node_index(self, index: QModelIndex) -> bool:
        return index.isValid() and self._nodes_model is not None and index.model() is self._nodes_model

    @staticmethod
    def _normalize_to_column0(index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        if index.column() == 0:
            return index
        return index.sibling(index.row(), 0)

    @staticmethod
    def _display_text(index: QPersistentModelIndex) -> str:
        if not index.isValid():
            return "<invalid>"

        value = index.data(Qt.DisplayRole)
        if value is None:
            return f"row={index.row()}"
        return str(value)
