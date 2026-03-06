from __future__ import annotations
from typing import Any, List, Optional

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


class RootItem:
    def __init__(self):
        self._nodes: List[ExpressionItem] = []
        self._model: weakref.ref[ExpressionsModel]|None = None

    def model(self) -> ExpressionsModel|None:
        if self._model:
            return self._model()
        else:
            return None
    
    def appendNode(self, node: ExpressionItem) -> bool:
        if node.model() != self.model():
            warnings.warn("Cannot add a node that belongs to a different model")
            return False
        model = self.model()
        if model is not None: model.beginInsertRows(QModelIndex(), len(self._nodes), len(self._nodes))
        self._nodes.append(node)
        node._root = self
        if model is not None: model.endInsertRows()
        return True

    def removeNode(self, node: ExpressionItem) -> None:
        if node in self._nodes:
            index = self._nodes.index(node)
            model = self.model()
            if model is not None: model.beginRemoveRows(QModelIndex(), index, index)
            self._nodes.remove(node)
            if model is not None: model.endRemoveRows()

    def nodes(self) -> List[ExpressionItem]:
        return [_ for _ in self._nodes]
    
    
class ExpressionItem:
    def __init__(self, name:str, expression: str=""):
        self._name = name
        self._expression = expression
        self._root: RootItem = RootItem()

    def __hash__(self):
        return hash((self._name, self._root))

    def inlets(self) -> List[InletItem]:
        return [InletItem("In", self)]
    
    def outlets(self) -> List[OutletItem]:
        return [OutletItem("Out", self)]

    def name(self) -> str:
        return self._name

    def setName(self, name: str) -> None:
        self._name = name

    def setExpression(self, expression: str) -> None:
        self._expression = expression

    def expression(self) -> str:
        return self._expression

    def model(self) -> ExpressionsModel|None:
        if not self._root:
            return None
        return self._root.model()

    # def appendInlet(self, inlet: InletItem) -> bool:
    #     if inlet.model() != self.model():
    #         warnings.warn("Cannot add an inlet that belongs to a different model")
    #         return False
    #     model = self.model()
    #     if model is not None: model.beginInsertRows(model.indexFromItem(self), len(self._inlets), len(self._inlets))
    #     self._inlets.append(inlet)
    #     inlet._node = self
    #     if model is not None: model.endInsertRows()
    #     return True

    # def appendOutlet(self, outlet: OutletItem) -> bool:
    #     if outlet.model() != self.model():
    #         warnings.warn("Cannot add an outlet that belongs to a different model")
    #         return False
    #     model = self.model()
    #     if model is not None: model.beginInsertRows(model.indexFromItem(self), len(self._inlets) + len(self._outlets), len(self._inlets) + len(self._outlets))
    #     self._outlets.append(outlet)
    #     outlet._node = self
    #     if model is not None: model.endInsertRows()
    #     return True

    # def removeInlet(self, inlet: InletItem) -> bool:
    #     if inlet not in self._inlets:
    #         return False
        
    #     index = self._inlets.index(inlet)
    #     model = self.model()
    #     if model is not None: model.beginRemoveRows(model.indexFromItem(self), index, index)
    #     self._inlets.remove(inlet)
    #     inlet._node = None
    #     if model is not None: model.endRemoveRows()
    #     return True

    # def removeOutlet(self, outlet: OutletItem) -> None:
    #     if outlet in self._outlets:
    #         index = self._outlets.index(outlet)
    #         model = self.model()
    #         if model is not None: model.beginRemoveRows(model.indexFromItem(self), len(self._inlets) + index, len(self._inlets) + index)
    #         self._outlets.remove(outlet)
    #         outlet._node = None
    #         if model is not None: model.endRemoveRows()



class InletItem:
    def __init__(self, name: str, node: ExpressionItem|None=None):
        self._name = name
        self._node: ExpressionItem|None = node

    def __hash__(self):
        return hash((self._name, self._node))

    def model(self) -> ExpressionsModel|None:
        if not self._node:
            return None
        return self._node.model()
    
    def name(self) -> str:
        return self._name
    
    def setName(self, name: str) -> None:
        self._name = name
    

class OutletItem:
    def __init__(self, name: str, node: ExpressionItem|None=None):
        self._name = name
        self._node: ExpressionItem|None = node

    def __hash__(self):
        return hash((self._name, self._node))

    def model(self) -> ExpressionsModel|None:
        if not self._node:
            return None
        return self._node.model()

    def name(self) -> str:
        return self._name
    
    def setName(self, name: str) -> None:
        self._name = name
    

class ExpressionsModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._root = RootItem()

    # -- Custom methods for managing nodes and sockets --
    def appendNode(self, node: ExpressionItem) -> bool:
        return self._root.appendNode(node)

    # -- QAbstractItemModel overrides --
    def itemFromIndex(self, index: QModelIndex) -> RootItem|ExpressionItem|InletItem|OutletItem:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self._root

    def indexFromItem(self, item: RootItem|ExpressionItem|InletItem|OutletItem) -> QModelIndex:
        if isinstance(item, RootItem):
            return QModelIndex()
        elif isinstance(item, ExpressionItem):
            root = item._root
            row = root._nodes.index(item)
            return self.createIndex(row, 0, item)
        elif isinstance(item, InletItem):
            node = cast(ExpressionItem, item._node)
            row = node._inlets.index(item)
            return self.createIndex(row, 0, item)
        elif isinstance(item, OutletItem):
            node = cast(ExpressionItem, item._node)
            row = len(node._inlets) + node._outlets.index(item)
            return self.createIndex(row, 0, item)
        else:
            raise TypeError(f"Unexpected item type: {item}")

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  
        match self.itemFromIndex(parent):
            case RootItem():
                root = self._root
                if row < 0 or row >= len(root._nodes):
                    return QModelIndex()
                node = root._nodes[row]
                return self.createIndex(row, column, node)
            
            case ExpressionItem():
                node = cast(ExpressionItem, self.itemFromIndex(parent))
                if row < 0 or row >= len(node._inlets) + len(node._outlets):
                    return QModelIndex()
                if row < len(node._inlets):
                    inlet = node._inlets[row]
                    return self.createIndex(row, column, inlet)
                else:
                    outlet = node._outlets[row - len(node._inlets)]
                    return self.createIndex(row, column, outlet)
                
            case InletItem() | OutletItem():
                raise ValueError("Sockets cannot have children")
            case _:
                raise TypeError(f"Unexpected item type: {self.itemFromIndex(parent)}")

    def parent(self, index: QModelIndex) -> QModelIndex: #type: ignore[override]
        if not index.isValid():
            return QModelIndex()

        child_item = self.itemFromIndex(index)
        match child_item:
            case ExpressionItem():
                return QModelIndex()
            
            case InletItem():
                inlet = cast(InletItem, child_item)
                node = inlet._node
                assert node is not None
                row = node._root._nodes.index(node)
                return self.createIndex(row, 0, node)

            case OutletItem():
                outlet = cast(OutletItem, child_item)
                node = outlet._node
                assert node is not None
                row = node._root._nodes.index(node)
                return self.createIndex(row, 0, node)

            case _:
                raise TypeError(f"Unexpected item type: {child_item}")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootItem():
                root = item
                return len(root._nodes)
            
            case ExpressionItem():
                node = item
                return len(node._inlets) + len(node._outlets)
            
            case InletItem():
                return 0

            case OutletItem():
                return 0

            case _:
                raise TypeError(f"Unexpected item type: {item}")

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self.itemFromIndex(parent)
        match item:
            case RootItem():
                return 2
            
            case ExpressionItem():
                return 1
            
            case InletItem():
                return 1

            case OutletItem():
                return 1

            case _:
                raise TypeError(f"Unexpected item type: {item}")
            
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["name", "expression"][section]
        else:
            return section
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        if index.column() >= 2:
            return False
        
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, GraphDataRole):
            return None

        item = self.itemFromIndex(index)
        if isinstance(item, ExpressionItem):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if index.column() == 0:
                    return item.name()
                elif index.column() == 1:
                    return item.expression()
            elif role == GraphDataRole:
                return GraphRole.Node
            
        elif isinstance(item, InletItem):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if index.column() == 0:
                    return item.name()
            elif role == GraphDataRole:
                return GraphRole.Inlet
            
        elif isinstance(item, OutletItem):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if index.column() == 0:
                    return item.name()
            elif role == GraphDataRole:
                return GraphRole.Outlet
            
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        print(f"setData called with index={index.row()} {index.column()}, value={value}, role={role}")
        if not index.isValid():
            return False

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return False
        
        if index.column() >= 2:
            return False

        item = self.itemFromIndex(index)
        match item:
            case ExpressionItem():
                if index.column() == 0:
                    node = cast(ExpressionItem, item)
                    node.setName(value if role == Qt.ItemDataRole.EditRole else str(value))
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                    return True
                
                elif index.column() == 1:
                    node = cast(ExpressionItem, item)
                    node.setExpression(value if role == Qt.ItemDataRole.EditRole else str(value))
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                    return True
            
            case InletItem():
                if index.column() == 0:
                    inlet = cast(InletItem, item)
                    inlet.setName(value if role == Qt.ItemDataRole.EditRole else str(value))
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                    return True

            
            case OutletItem():
                if index.column() == 0:
                    outlet = cast(OutletItem, item)
                    outlet.setName(value if role == Qt.ItemDataRole.EditRole else str(value))
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                    return True

            

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
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
                    new_node = ExpressionItem(name=f"Node {len(self._root._nodes)}", _graph=self._root)
                    self._root._nodes.insert(row + offset, new_node)
                self.endInsertRows()
                return True
            
            case ExpressionItem():
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
            
            case ExpressionItem():
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
    
    
