from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Literal, cast
import warnings

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
import weakref

GraphDataRole = Qt.ItemDataRole.UserRole+10

from enum import StrEnum
class GraphRole(StrEnum):
    Node = "Node"
    Inlet = "Inlet"
    Outlet = "Outlet"

from contextlib import contextmanager

@dataclass
class RootItem:
    _nodes: List[NodeItem] = field(default_factory=list)
    _model: weakref.ref[StandardNodesModel] = field(default_factory=lambda: weakref.ref(None))

    def model(self) -> StandardNodesModel|None:
        return self._model()

    @contextmanager
    def insert_rows(self, parent: QModelIndex, row: int, count: int):
        model = self._model()
        if model is not None:
            model.beginInsertRows(parent, row, row + count - 1)
            try:
                yield
            finally:
                model.endInsertRows()
        else:
            yield

    def appendNode(self, node: NodeItem) -> None:
        model = self._model()
        if model is not None: model.beginInsertRows(QModelIndex(), len(self._nodes), len(self._nodes))
        self._nodes.append(node)
        if model is not None: model.endInsertRows()

    def removeNode(self, node: NodeItem) -> None:
        if node in self._nodes:
            index = self._nodes.index(node)
            model = self._model()
            if model is not None: model.beginRemoveRows(QModelIndex(), index, index)
            self._nodes.remove(node)
            if model is not None: model.endRemoveRows()

    @property
    def nodes(self) -> List[NodeItem]:
        return [_ for _ in self._nodes]
    
    
@dataclass
class NodeItem:
    name: str
    _graph: RootItem|None = None
    _inlets: List[InletData] = field(default_factory=list)
    _outlets: List[OutletData] = field(default_factory=list)

    @property
    def model(self) -> StandardNodesModel|None:
        if not self._graph:
            return None
        
        return self._graph.model()

    def appendInlet(self, inlet: InletData) -> None:
        model = self._model()
        if model is not None: model.beginInsertRows(model.indexFromItem(self), len(self._inlets), len(self._inlets))
        self._inlets.append(inlet)
        inlet._node = self
        if model is not None: model.endInsertRows()

    def appendOutlet(self, outlet: OutletData) -> None:
        model = self._model()
        if model is not None: model.beginInsertRows(model.indexFromItem(self), len(self._inlets) + len(self._outlets), len(self._inlets) + len(self._outlets))
        self._outlets.append(outlet)
        outlet._node = self
        if model is not None: model.endInsertRows()

    def removeInlet(self, inlet: InletData) -> None:
        if inlet in self._inlets:
            index = self._inlets.index(inlet)
            model = self._model()
            if model is not None: model.beginRemoveRows(model.indexFromItem(self), index, index)
            self._inlets.remove(inlet)
            inlet._node = None
            if model is not None: model.endRemoveRows()

    def removeOutlet(self, outlet: OutletData) -> None:
        if outlet in self._outlets:
            index = self._outlets.index(outlet)
            model = self._model()
            if model is not None: model.beginRemoveRows(model.indexFromItem(self), len(self._inlets) + index, len(self._inlets) + index)
            self._outlets.remove(outlet)
            outlet._node = None
            if model is not None: model.endRemoveRows()


@dataclass
class InletData:
    name: str
    _node: NodeItem

    def model(self) -> StandardNodesModel|None:
        if self._node is None:
            return None
        return self._node.model()
    

@dataclass
class OutletData:
    name: str
    _node: NodeItem

    def model(self) -> StandardNodesModel|None:
        if self._node is None:
            return None
        return self._node.model()



class StandardNodesModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._headers: List[str] = ["expression"]
        self._root = RootItem()

    # -- Custom methods for managing nodes and sockets --
    def appendNode(self, node: NodeItem) -> bool:
        parent = QModelIndex()
        root = cast(RootItem, self.itemFromIndex(parent))
        node_count = len(root._nodes)
        self.beginInsertRows(parent, node_count, node_count)
        root = cast(RootItem, self.itemFromIndex(parent))
        root.appendNode(node)
        
        self.endInsertRows()
        return True
    
    def appendInlet(self, node_index: QModelIndex, name:str) -> bool:
        if not node_index.isValid():
            return False
        node = cast(NodeItem, self.itemFromIndex(node_index))
        inlet_count = len(node._inlets)
        self.beginInsertRows(node_index, inlet_count, inlet_count)
        node = cast(NodeItem, self.itemFromIndex(node_index))
        new_inlet = InletData(name=name, _node=node)
        node._inlets.insert(inlet_count, new_inlet)
        self.endInsertRows()
        return True
    
    def appendOutlet(self, node_index: QModelIndex, name:str) -> bool:
        if not node_index.isValid():
            return False
        node = cast(NodeItem, self.itemFromIndex(node_index))
        outlet_count = len(node._outlets)
        row = len(node._inlets) + outlet_count
        self.beginInsertRows(node_index, row, row)
        node = cast(NodeItem, self.itemFromIndex(node_index))
        new_outlet = OutletData(name=name, _node=node)
        node._outlets.insert(outlet_count, new_outlet)
        self.endInsertRows()
        return True

    # -- QAbstractItemModel overrides --
    def itemFromIndex(self, index: QModelIndex) -> RootItem|NodeItem|InletData|OutletData:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self._root

    def indexFromItem(self, item: RootItem|NodeItem|InletData|OutletData) -> QModelIndex:
        if isinstance(item, RootItem):
            return QModelIndex()
        elif isinstance(item, NodeItem):
            root = item._graph
            row = root._nodes.index(item)
            return self.createIndex(row, 0, item)
        elif isinstance(item, InletData):
            node = item._node
            row = node._inlets.index(item)
            return self.createIndex(row, 0, item)
        elif isinstance(item, OutletData):
            node = item._node
            row = len(node._inlets) + node._outlets.index(item)
            return self.createIndex(row, 0, item)
        else:
            raise TypeError(f"Unexpected item type: {item}")

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  
        match self.itemFromIndex(parent):
            case RootItem():
                root = self.itemFromIndex(parent)
                if row < 0 or row >= len(root._nodes):
                    return QModelIndex()
                node = root._nodes[row]
                return self.createIndex(row, column, node)
            
            case NodeItem():
                node = self.itemFromIndex(parent)
                if row < 0 or row >= len(node._inlets) + len(node._outlets):
                    return QModelIndex()
                if row < len(node._inlets):
                    inlet = node._inlets[row]
                    return self.createIndex(row, column, inlet)
                else:
                    outlet = node._outlets[row - len(node._inlets)]
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
            case NodeItem():
                return QModelIndex()
            
            case InletData():
                inlet = child_item
                node = child_item._node
                row = node._graph._nodes.index(node)
                return self.createIndex(row, 0, node)

            case OutletData():
                outlet = child_item
                node = child_item._node
                row = node._graph._nodes.index(node)
                return self.createIndex(row, 0, node)

            case _:
                raise TypeError(f"Unexpected item type: {child_item}")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootItem():
                root = item
                return len(root._nodes)
            
            case NodeItem():
                node = item
                return len(node._inlets) + len(node._outlets)
            
            case InletData():
                return 0

            case OutletData():
                return 0

            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootItem():
                return 1
            
            case NodeItem():
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
        if isinstance(item, NodeItem):
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
            case NodeItem():
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

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)
        if row < 0 or row > parent_item.child_count():
            return False
        
        match parent_item:
            case RootItem():
                # Adding a new node to the root
                self.beginInsertRows(parent, row, row + count - 1)
                for offset in range(count):
                    new_node = NodeItem(name=f"Node {len(self._root._nodes)}", _graph=self._root)
                    self._root._nodes.insert(row + offset, new_node)
                self.endInsertRows()
                return True
            
            case NodeItem():
                warnings.warn("Sockets should be added using insertInlet and insertOutlet methods")
                return False
            case _:
                return False

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)

        match parent_item:
            case RootItem():
                root = parent_item
                if row < 0 or row + count > len(root._nodes):
                    return False
                self.beginRemoveRows(parent, row, row + count - 1)
                for _ in range(count):
                    del root._nodes[row]
                self.endRemoveRows()
                return True
            
            case NodeItem():
                node = parent_item
                if row < 0 or row + count > len(node._inlets) + len(node._outlets):
                    return False
                self.beginRemoveRows(parent, row, row + count - 1)
                for _ in range(count):
                    del node._inlets[row]
                self.endRemoveRows()
                return True
            
            case _:
                return False
    
    
