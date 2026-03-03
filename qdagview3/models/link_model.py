from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, QPersistentModelIndex, Qt


@dataclass(slots=True)
class LinkData:
    source: QPersistentModelIndex
    target: QPersistentModelIndex

    def _post_init__(self):
        if not self.source.isValid():
            raise ValueError(f"Source index must be valid, got: {self.source}")
        if not self.target.isValid():
            raise ValueError(f"Target index must be valid, got: {self.target}")


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
        self._links: list[LinkData] = []
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
        assert isinstance(source, QModelIndex), f"Source and source must be QModelIndex instances, got {type(source)} instead"
        assert isinstance(target, QModelIndex), f"Source and target must be QModelIndex instances, got {type(target)} instead"
        assert source.isValid(), f"Source index must be valid, got: {source}"
        assert target.isValid(), f"Target index must be valid, got: {target}"

        source_col0 = self._normalize_to_column0(source)
        target_col0 = self._normalize_to_column0(target)

        if not self._is_valid_node_index(source_col0) or not self._is_valid_node_index(target_col0):
            return -1

        row = len(self._links)
        self.beginInsertRows(QModelIndex(), row, row)
        self._links.append(
            LinkData(
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

        self._links[row] = LinkData(
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
    
    def linkSource(self, link_index: QModelIndex) -> QModelIndex:
        assert isinstance(link_index, QModelIndex), f"link_index must be a QModelIndex instance, got {type(link_index)} instead"
        assert link_index.isValid(), f"link_index must be valid, got: {link_index}"
        assert link_index.column() == 0, f"link_index must be in column 0, got column {link_index.column()} instead"
        if not (0 <= link_index.row() < len(self._links)):
            raise IndexError(f"link_index row {link_index.row()} is out of range")

        persistent_index = self._links[link_index.row()].source
        return QModelIndex(persistent_index)

    def linkTarget(self, index: QModelIndex) -> QModelIndex|None:
        assert isinstance(index, QModelIndex), f"index must be a QModelIndex instance, got {type(index)} instead"
        assert index.isValid(), f"index must be valid, got: {index}"
        assert index.column() == 0, f"index must be in column 0, got column {index.column()} instead"
        if not (0 <= index.row() < len(self._links)):
            raise IndexError(f"index row {index.row()} is out of range")
        
        persistent_index = self._links[index.row()].target
        return QModelIndex(persistent_index)

    def links_connected_to(self, port_index: QModelIndex) -> list[QModelIndex]:
        """Return a list of link indexes connected to the given port index."""
        assert isinstance(port_index, QModelIndex), f"port_index must be a QModelIndex instance, got {type(port_index)} instead"
        assert port_index.isValid(), f"port_index must be valid, got: {port_index}"
        assert port_index.column() == 0, f"port_index must be in column 0, got column {port_index.column()} instead"
        if not self._is_valid_node_index(port_index):
            raise ValueError(f"port_index is not from the nodes model: {port_index}")

        connected_links = []
        for row, link in enumerate(self._links): #TODO: optimize by maintaining a mapping of node index to connected link indexes
            if link.source == port_index or link.target == port_index:
                connected_links.append(self.index(row, 0))
        return connected_links

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
        model.rowsAboutToBeRemoved.connect(self._on_nodes_rows_about_to_be_removed)
        model.rowsRemoved.connect(self._on_nodes_model_changed)
        model.modelReset.connect(self._on_nodes_model_changed)
        model.layoutChanged.connect(self._on_nodes_model_changed)
        model.destroyed.connect(self._on_nodes_model_destroyed)

    def _disconnect_nodes_model(self, model: QAbstractItemModel) -> None:
        self._safe_disconnect(model.rowsAboutToBeRemoved, self._on_nodes_rows_about_to_be_removed)
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

    def _on_nodes_rows_about_to_be_removed(self, parent: QModelIndex, first: int, last: int) -> None:
        """Remove links that touch any node in the subtree being removed."""
        rows_to_remove: list[int] = []
        for row, link in enumerate(self._links):
            source_index = QModelIndex(link.source)
            target_index = QModelIndex(link.target)

            if (
                self._is_in_removed_subtree(source_index, parent, first, last)
                or self._is_in_removed_subtree(target_index, parent, first, last)
            ):
                rows_to_remove.append(row)

        for row in reversed(rows_to_remove):
            self.remove_link(row)

    def _on_nodes_model_destroyed(self, obj: QObject) -> None:
        del obj
        self._nodes_model = None
        self.clear_links()

    def _is_valid_node_index(self, index: QModelIndex) -> bool:
        return index.isValid() and self._nodes_model is not None and index.model() is self._nodes_model

    @staticmethod
    def _is_in_removed_subtree(index: QModelIndex, parent: QModelIndex, first: int, last: int) -> bool:
        """Return True if index is inside one of parent's rows [first, last] being removed."""
        if not index.isValid():
            return False

        current = index
        while current.isValid():
            current_parent = current.parent()
            if current_parent == parent:
                return first <= current.row() <= last
            current = current_parent

        # Handles top-level removals where parent is invalid.
        return not parent.isValid() and first <= index.row() <= last

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
