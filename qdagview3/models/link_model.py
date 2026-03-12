from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from qtpy.QtCore import Signal

from qdagview3.utils.graphutils import group_consecutive_numbers

@dataclass(slots=True)
class LinkData:
    source: QPersistentModelIndex
    target: QPersistentModelIndex

    def __post_init__(self):
        if not self.source.isValid():
            raise ValueError(f"Source index must be valid, got: {self.source}")
        if not self.target.isValid():
            raise ValueError(f"Target index must be valid, got: {self.target}")


class LinkModel(QAbstractItemModel):
    """Flat 2-column model storing links between source-model rows.

    Column 0 stores the source row index (persisted as QPersistentModelIndex).
    Column 1 stores the target row index (persisted as QPersistentModelIndex).
    """
    nodesModelChanged = Signal()

    def __init__(self, nodes_model: QAbstractItemModel, parent=None) -> None:
        super().__init__(parent)
        self._headers = ("Source", "Target")
        self._links: list[LinkData] = []
        self._nodes_model: QAbstractItemModel|None = None
        self._nodes_model_connections = []

        self.setNodesModel(nodes_model)

    # QAbstractItemModel implementation
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() or not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex) -> QModelIndex: #type: ignore[override]
        del child
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._links)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        del parent
        return 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if not (0 <= index.row() < len(self._links)):
            return None

        def node_display_text(node_index: QPersistentModelIndex) -> str:
            if not node_index.isValid():
                return "<invalid>"
            
            dotted_path = []
            current = node_index
            while current.isValid():
                value = current.data(Qt.ItemDataRole.DisplayRole)
                if value:
                    dotted_path.append(str(value))
                else:
                    dotted_path.append(f"row={current.row()}")
                current = current.parent()

            return ".".join(reversed(dotted_path))
            
        link: LinkData = self._links[index.row()]
        match index.column():
            case 0:
                node_index: QPersistentModelIndex = link.source
                match role:
                    case Qt.ItemDataRole.DisplayRole:
                        return node_display_text(node_index)
                    case Qt.ItemDataRole.EditRole:
                        return node_index
                    case _:
                        return None
            case 1:
                node_index: QPersistentModelIndex = link.target
                match role:
                    case Qt.ItemDataRole.DisplayRole:
                        return node_display_text(node_index)
                    case Qt.ItemDataRole.EditRole:
                        return node_index
                    case _:
                        return None
            case _:
                return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        if 0 <= section < len(self._headers):
            return self._headers[section]
        return None

    # Public API for managing links and nodes model
    def nodesModel(self) -> QAbstractItemModel:
        return self._nodes_model

    def setNodesModel(self, nodes_model: QAbstractItemModel) -> None:
        if self._nodes_model is nodes_model:
            return

        if self._nodes_model is not None:
            for signal, slot in self._nodes_model_connections:
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
            self._nodes_model_connections = []
            self._nodes_model = None

        if nodes_model is not None:
            nodes_model_connections = [
                (nodes_model.rowsAboutToBeRemoved, self._on_nodes_rows_about_to_be_removed),
                (nodes_model.rowsRemoved,          self._on_nodes_model_changed),
                (nodes_model.modelReset,           self._on_nodes_model_changed),
                (nodes_model.layoutChanged,        self._on_nodes_model_changed),
                (nodes_model.destroyed,            self._on_nodes_model_destroyed)
            ]
            for signal, slot in nodes_model_connections:
                signal.connect(slot)
            self._nodes_model_connections = nodes_model_connections
            self._nodes_model = nodes_model

        self.clear_links()
        self.nodesModelChanged.emit()

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

        self.remove_links(rows_to_remove)

    def _on_nodes_model_destroyed(self, obj: QObject) -> None:
        del obj
        self._nodes_model = None
        self.clear_links()

    def insert_link(self, source: QModelIndex, target: QModelIndex, pos: int) -> bool:
        """Insert a link at the specified position and return its row index.

        Both source and target are normalized to column 0 before persisting.
        """
        assert isinstance(source, QModelIndex), f"Source and source must be QModelIndex instances, got {type(source)} instead"
        assert isinstance(target, QModelIndex), f"Source and target must be QModelIndex instances, got {type(target)} instead"
        assert source.isValid(), f"Source index must be valid, got: {source}"
        assert target.isValid(), f"Target index must be valid, got: {target}"

        source_col0 = self._normalize_to_column0(source)
        target_col0 = self._normalize_to_column0(target)

        if not self._is_valid_node_index(source_col0) or not self._is_valid_node_index(target_col0):
            return False

        row = len(self._links)
        self.beginInsertRows(QModelIndex(), row, row)
        self._links.insert(
            pos,
            LinkData(
                source=QPersistentModelIndex(source_col0),
                target=QPersistentModelIndex(target_col0),
            )
        )
        self.endInsertRows()
        return True

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
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )
        return True

    def remove_link(self, row: int) -> bool:
        if not (0 <= row < len(self._links)):
            return False

        self.beginRemoveRows(QModelIndex(), row, row)
        self._links.pop(row)
        self.endRemoveRows()
        return True

    # def remove_links(self, rows: list[int]) -> int:
    #     """Remove multiple links at once, grouping consecutive rows into ranges."""
    #     if not rows:
    #         return 0
    #     removed = 0
    #     # Process ranges in reverse order so row indices stay valid
    #     for r in reversed(list(group_consecutive_numbers(sorted(rows)))):
    #         self.beginRemoveRows(QModelIndex(), r.start, r.stop - 1)
    #         del self._links[r.start:r.stop]
    #         self.endRemoveRows()
    #         removed += len(r)
    #     return removed
    
    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if parent.isValid():
            return False
        
        if not (0 <= row < len(self._links)) or not (0 <= row + count - 1 < len(self._links)):
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        del self._links[row:row + count]
        self.endRemoveRows()
        return True
    
    def remove_links(self, rows: list[int]) -> int:
        """Remove multiple links at once, grouping consecutive rows into ranges."""

        # - group selected rows into continuous ranges to minimize number of removeRows calls -
        continous_selected_rows:List[List[int]] = []
        for row in sorted(rows):
            if not continous_selected_rows or row != continous_selected_rows[-1][-1] + 1:
                continous_selected_rows.append([row])
            else:
                continous_selected_rows[-1].append(row)

        for rows in reversed(continous_selected_rows):
            self.removeRows(rows[0], len(rows), QModelIndex())

    def linkSource(self, link_index: QModelIndex) -> QModelIndex:
        assert isinstance(link_index, QModelIndex), f"link_index must be a QModelIndex instance, got {type(link_index)} instead"
        assert link_index.isValid(), f"link_index must be valid, got: {link_index}"
        assert link_index.column() == 0, f"link_index must be in column 0, got column {link_index.column()} instead"
        if not (0 <= link_index.row() < len(self._links)):
            raise IndexError(f"link_index row {link_index.row()} is out of range")

        persistent_index = self._links[link_index.row()].source
        return QModelIndex(persistent_index)

    def linkTarget(self, index: QModelIndex) -> QModelIndex:
        assert isinstance(index, QModelIndex), f"index must be a QModelIndex instance, got {type(index)} instead"
        assert index.isValid(), f"index must be valid, got: {index}"
        assert index.column() == 0, f"index must be in column 0, got column {index.column()} instead"
        if not (0 <= index.row() < len(self._links)):
            raise IndexError(f"index row {index.row()} is out of range")
        
        persistent_index = self._links[index.row()].target
        return QModelIndex(persistent_index)

    def linksConnectedTo(self, port_index: QModelIndex) -> list[QModelIndex]:
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

    def remove_invalid_links(self) -> int:
        """Remove links whose source or target index is no longer valid."""
        invalid_rows = [
            row
            for row, link in enumerate(self._links)
            if not link.source.isValid() or not link.target.isValid()
        ]
        return self.remove_links(invalid_rows)

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

    def _is_valid_node_index(self, index: QModelIndex) -> bool:
        return index.isValid() and self._nodes_model is not None and index.model() is self._nodes_model

    #@override
    def moveRows(self, sourceParent:QModelIndex, sourceRow:int, count:int, destinationParent:QModelIndex, destinationChild:int) -> bool:
        """Override moveRows to update link indexes when nodes are moved within the nodes model."""

        if sourceParent.isValid() or destinationParent.isValid():
            # links model is a lfat structure. there are not supposed to be any parent-child relationships.
            return False
        
        # Validate source ranges
        if not (0 <= sourceRow < len(self._links)) or not (0 <= sourceRow + count - 1 < len(self._links)):
            return False
        
        # Validate destination ranges
        if not (0 <= destinationChild <= len(self._links)):
            return False
        
        # Perform the move
        self.beginMoveRows(sourceParent, sourceRow, sourceRow + count - 1, destinationParent, destinationChild)
        left = self._links[:sourceRow] 
        middle = self._links[sourceRow : sourceRow + count]
        right = self._links[sourceRow + count:]

        self._links = left + right  # remove the moved links from the list temporarily
        self._links[destinationChild:destinationChild] = middle # insert the moved links at the destination

        self.endMoveRows()
        
        return True

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

    def toNetworkX(self)->'networkx.MultiDiGraph[QModelIndex]':
        """return links between root_rows as a networkx MultiDiGraph"""
        import networkx as nx
        G = nx.MultiDiGraph()
        nodes_model = self.nodesModel()

        # for each endpoint, find the root node:
        def get_index_root_node(idx:QModelIndex) -> QModelIndex:
            while idx.parent().isValid():
                idx = idx.parent()
            return idx

        for node_row in range(nodes_model.rowCount(QModelIndex())):
            node_index = nodes_model.index(node_row, 0, QModelIndex())
            node_index = get_index_root_node(node_index)

            G.add_node(node_index, name=nodes_model.data(node_index, Qt.ItemDataRole.DisplayRole))

        for link_row in range(self.rowCount(QModelIndex())):
            link_index = self.index(link_row, 0, QModelIndex())

            source_index = self.linkSource(link_index)
            target_index = self.linkTarget(link_index)

            source_index = get_index_root_node(source_index)
            target_index = get_index_root_node(target_index)

            G.add_edge(source_index, target_index)

        return G