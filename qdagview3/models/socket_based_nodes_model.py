from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Literal, cast
import warnings

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt


GraphDataRole = Qt.ItemDataRole.UserRole+10

from enum import StrEnum
class GraphRole(StrEnum):
    Node = "Node"
    Inlet = "Inlet"
    Outlet = "Outlet"



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


class SocketBasedNodesModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._headers: List[str] = ["expression"]
        self._root = RootData()

    def itemFromIndex(self, index: QModelIndex) -> RootData|NodeData|InletData|OutletData:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self._root

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  
        match self.itemFromIndex(parent):
            case RootData():
                root = self.itemFromIndex(parent)
                if row < 0 or row >= len(root.nodes):
                    return QModelIndex()
                node = root.nodes[row]
                return self.createIndex(row, column, node)
            case NodeData():
                node = self.itemFromIndex(parent)
                if row < 0 or row >= len(node.inlets) + len(node.outlets):
                    return QModelIndex()
                if row < len(node.inlets):
                    inlet = node.inlets[row]
                    return self.createIndex(row, column, inlet)
                else:
                    outlet = node.outlets[row - len(node.inlets)]
                    return self.createIndex(row, column, outlet)
            case InletData() | OutletData():
                raise ValueError("Sockets cannot have children")
            case _:
                raise TypeError(f"Unexpected item type: {self.itemFromIndex(parent)}")

    def parent(self, index: QModelIndex) -> QModelIndex: #type: ignore[override]
        if not index.isValid():
            return QModelIndex()

        child_item = self.itemFromIndex(index)
        match child_item:
            case NodeData():
                return QModelIndex()
            
            case InletData():
                inlet = child_item
                node = child_item.node
                row = node.graph.nodes.index(node)
                return self.createIndex(row, 0, node)

            case OutletData():
                outlet = child_item
                node = child_item.node
                row = node.graph.nodes.index(node)
                return self.createIndex(row, 0, node)

            case _:
                raise TypeError(f"Unexpected item type: {child_item}")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootData():
                root = item
                return len(root.nodes)
            
            case NodeData():
                node = item
                return len(node.inlets) + len(node.outlets)
            
            case InletData():
                return 0

            case OutletData():
                return 0

            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootData():
                return 1
            
            case NodeData():
                return 1
            
            case InletData():
                return 1

            case OutletData():
                return 1

            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        if index.column() != 0:
            return None
        
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, GraphDataRole):
            return None

        item = self.itemFromIndex(index)
        if isinstance(item, NodeData):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return item.name
            elif role == GraphDataRole:
                return GraphRole.Node
        elif isinstance(item, InletData):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return item.name
            elif role == GraphDataRole:
                return GraphRole.Inlet
        elif isinstance(item, OutletData):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return item.name
            elif role == GraphDataRole:
                return GraphRole.Outlet
        return None


    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return False
        
        if index.column() != 0:
            return False

        item = self.itemFromIndex(index)
        match item:
            case NodeData():
                node = item
                node.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case InletData():
                inlet = item
                inlet.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case OutletData():
                outlet = item
                outlet.name = value if role == Qt.ItemDataRole.EditRole else str(value)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case _:
                return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    # def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
    #     if orientation == Qt.Orientation.Horizontal and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
    #         if 0 <= section < len(self._headers):
    #             return self._headers[section]
            
    #     if orientation == Qt.Orientation.Vertical and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
    #         return f"{section}"
    #     return None

    # def setHeaderData(
    #     self,
    #     section: int,
    #     orientation: Qt.Orientation,
    #     value,
    #     role: int = Qt.ItemDataRole.EditRole,
    # ) -> bool:
    #     if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.EditRole:
    #         return False
    #     if not (0 <= section < len(self._headers)):
    #         return False

    #     self._headers[section] = str(value)
    #     self.headerDataChanged.emit(orientation, section, section)
    #     return True

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)
        if row < 0 or row > parent_item.child_count():
            return False
        
        match parent_item:
            case RootData():
                # Adding a new node to the root
                self.beginInsertRows(parent, row, row + count - 1)
                for offset in range(count):
                    new_node = NodeData(name=f"Node {len(self._root.nodes)}", graph=self._root)
                    self._root.nodes.insert(row + offset, new_node)
                self.endInsertRows()
                return True
            
            case NodeData():
                warnings.warn("Sockets should be added using insertInlet and insertOutlet methods")
                return False
            case _:
                return False

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)

        match parent_item:
            case RootData():
                root = parent_item
                if row < 0 or row + count > len(root.nodes):
                    return False
                self.beginRemoveRows(parent, row, row + count - 1)
                for _ in range(count):
                    del root.nodes[row]
                self.endRemoveRows()
                return True
            
            case NodeData():
                node = parent_item
                if row < 0 or row + count > len(node.inlets) + len(node.outlets):
                    return False
                self.beginRemoveRows(parent, row, row + count - 1)
                for _ in range(count):
                    del node.inlets[row]
                self.endRemoveRows()
                return True
            
            case _:
                return False
            
    def appendNode(self, name:str) -> bool:
        parent = QModelIndex()
        root = cast(RootData, self.itemFromIndex(parent))
        node_count = len(root.nodes)
        self.beginInsertRows(parent, node_count, node_count)
        root = cast(RootData, self.itemFromIndex(parent))
        new_node = NodeData(name=name, graph=root)
        root.nodes.insert(node_count, new_node)
        self.endInsertRows()
        return True
    
    def appendInlet(self, node_index: QModelIndex, name:str) -> bool:
        if not node_index.isValid():
            return False
        node = cast(NodeData, self.itemFromIndex(node_index))
        inlet_count = len(node.inlets)
        self.beginInsertRows(node_index, inlet_count, inlet_count)
        node = cast(NodeData, self.itemFromIndex(node_index))
        new_inlet = InletData(name=name, node=node)
        node.inlets.insert(inlet_count, new_inlet)
        self.endInsertRows()
        return True
    
    def appendOutlet(self, node_index: QModelIndex, name:str) -> bool:
        if not node_index.isValid():
            return False
        node = cast(NodeData, self.itemFromIndex(node_index))
        outlet_count = len(node.outlets)
        row = len(node.inlets) + outlet_count
        self.beginInsertRows(node_index, row, row)
        node = cast(NodeData, self.itemFromIndex(node_index))
        new_outlet = OutletData(name=name, node=node)
        node.outlets.insert(outlet_count, new_outlet)
        self.endInsertRows()
        return True
