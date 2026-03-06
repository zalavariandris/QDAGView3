from __future__ import annotations
print("Loading expression model...")
from typing import List, Tuple, Iterable
import ast
from dataclasses import dataclass
from typing import Any, Optional, cast
import warnings
import weakref

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt

from qdagview3.models.socket_based_nodes_model import GraphDataRole, GraphRole

import random
import string
import re
from qdagview3.evaluate_python import find_unbounded_names, format_exception

def make_unique_id(length:int=8)->str:
    # Generate a random string of the specified length from ASCII letters and digits
    characters = string.ascii_uppercase
    unique_id = "".join(random.choices(characters, k=length))
    return unique_id


def make_unique_name(name:str, names:Iterable[str])->str:
    # Regex to extract the name part (without trailing digits)
    names = set(_ for _ in names)
    match = re.search(r"(.*?)(\d*)$", name)
    if match:
        # Name part without digits
        name_part = match.group(1)

        # Loop to find a unique name
        digit = 1
        while name in names:
            # Append the current digit to the name part
            name = f"{name_part}{digit}"
            digit += 1

    return name

def _group_consecutive_numbers_readable(numbers:list[int])->Iterable[range]:
    if not len(numbers)>0:
        return []

    first = last = numbers[0]
    for n in numbers[1:]:
        if n - 1 == last: # Part of the group, bump the end
            last = n
        else: # Not part of the group, yield current group and start a new
            yield range(first, last+1)
            first = last = n
    yield range(first, last+1) # Yield the last group


class ExpressionsModel(QAbstractItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        print("Initializing ExpressionsModel")
        self._nodes: List[str] = []
        self._expressions: dict[str, str] = {}
        
    def insertNodes(self, pos: int, names: List[str]) -> bool:
        if pos < 0 or pos > len(self._nodes):
            return False
        
        for name in names:
            if name in self._nodes:
                warnings.warn(f"Node with name '{name}' already exists. Node names must be unique.")
                return False
        
        self.beginInsertRows(QModelIndex(), pos, pos + len(names) - 1)
        for i, name in enumerate(names, start=pos):
            self._nodes.insert(i, name)
            self._expressions[name] = ""
        self.endInsertRows()
        print("Inserted nodes:", names)
        return True
    
    def removeNodes(self, names: List[str]) -> bool:
        name_to_row = {name: row for row, name in enumerate(self._nodes)}
        rows_to_remove = sorted((name_to_row[name] for name in names if name in name_to_row), reverse=True)

        continous_row_groups = list(_group_consecutive_numbers_readable(rows_to_remove))
        
        for continous_rows in continous_row_groups:
            self.beginRemoveRows(QModelIndex(), continous_rows.start, continous_rows.stop - 1)
            for row in reversed(range(continous_rows.start, continous_rows.stop)):
                node_name = self._nodes.pop(row)
                del self._expressions[node_name]
            self.endRemoveRows()
        return True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            # top-level: number of nodes
            return len(self._nodes)
        elif parent.isValid() and not parent.parent().isValid():
            # assert parent.parent().isValid() == False
            # node level: number of inlets + outlets
            node_name = self._nodes[parent.row()]
            inlets = self._get_inlet_names(node_name)
            outlets = self._get_outlet_names(node_name)
            return len(inlets) + len(outlets)
        else:
            return 0
        
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 2
        
    def inlets(self, node_index: QModelIndex) -> List[QModelIndex]:
        if not node_index.isValid() or node_index.parent().isValid():
            raise ValueError("Invalid node index")
        node_name = self._nodes[node_index.row()]
        inlet_names = self._get_inlet_names(node_name)
        return [self.index(i, 0, node_index) for i in range(len(inlet_names))]
    
    def outlets(self, node_index: QModelIndex) -> List[QModelIndex]:
        if not node_index.isValid() or node_index.parent().isValid():
            raise ValueError("Invalid node index")
        node_name = self._nodes[node_index.row()]
        outlet_names = self._get_outlet_names(node_name)
        inlet_count = len(self._get_inlet_names(node_name))
        return [self.index(i + inlet_count, 0, node_index) for i in range(len(outlet_names))]
        
    def _get_inlet_names(self, node_name: str) -> List[str]:
        expression = self._expressions[node_name]
        try:
            return find_unbounded_names(expression)
        except SyntaxError as e:
            return []
        except Exception as e:
            return []
    
    def _get_outlet_names(self, node_name: str) -> List[str]:
        return ["out"]

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if row < 0 or column < 0:
            return QModelIndex()

        if not parent.isValid():
            # top-level: nodes
            if row >= len(self._nodes):
                return QModelIndex()
            return self.createIndex(row, column)
        elif parent.isValid() and not parent.parent().isValid():
            # assert parent.parent().isValid() == False
            node_name = self._nodes[parent.row()]
            inlet_names = self._get_inlet_names(node_name)
            outlet_names = self._get_outlet_names(node_name)
            if row < len(inlet_names):
                return self.createIndex(row, column, node_name)
            elif row < len(inlet_names) + len(outlet_names):
                return self.createIndex(row, column, node_name)
            else:
                return QModelIndex()
        else:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        if index.internalPointer() is None:
            # top-level: nodes have no parent
            return QModelIndex()
        else:
            # node level: parent is the node
            node_name = index.internalPointer()
            try:
                node_row = self._nodes.index(node_name)
                return self.index(node_row, 0, QModelIndex())
            except ValueError:
                return QModelIndex()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = ["name", "expression"]
            if 0 <= section < len(headers):
                return headers[section]
            return None
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return section
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        IsNode = index.internalPointer() is None
        IsInlet = not IsNode and index.row() < len(self._get_inlet_names(index.internalPointer()))
        IsOutlet = not IsNode and not IsInlet

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if IsNode:
                node_name = self._nodes[index.row()]
                if index.column() == 0:
                    return node_name
                elif index.column() == 1:
                    return self._expressions[node_name]
                
            elif IsInlet:
                node_name = index.internalPointer()
                inlet_names = self._get_inlet_names(node_name)
                inlet_name = inlet_names[index.row()]
                if index.column() == 0:
                    return inlet_name
                elif index.column() == 1:
                    return ""
                
            elif IsOutlet:
                node_name = index.internalPointer()
                outlet_names = self._get_outlet_names(node_name)
                outlet_name = outlet_names[index.row() - len(self._get_inlet_names(node_name))]
                if index.column() == 0:
                    return outlet_name
                elif index.column() == 1:
                    return ""
                
        if role == GraphDataRole:
            if IsNode:
                return GraphRole.Node
            if IsInlet:
                return GraphRole.Inlet
            elif IsOutlet:
                return GraphRole.Outlet
            
        return None

    def setData(self, node_index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if (node_index.isValid() 
            and not node_index.parent().isValid() 
            and node_index.column() == 1 
            and role == Qt.ItemDataRole.EditRole
        ):
            node_name = self._nodes[node_index.row()]
            old_expression = self._expressions[node_name]
            new_expression = str(value)
            if old_expression == new_expression:
                return False
            
            try:
                old_unbound_names = find_unbounded_names(old_expression)
            except SyntaxError as e:
                old_unbound_names = []
            except Exception as e:
                old_unbound_names = []

            try:
                new_unbound_names = find_unbounded_names(new_expression)
            except SyntaxError as e:
                new_unbound_names = []
            except Exception as e:
                new_unbound_names = []

            # Parent for begin/endInsert/RemoveRows must be column 0
            parent_index = node_index.sibling(node_index.row(), 0)

            if len(new_unbound_names) > len(old_unbound_names):
                pos = len(old_unbound_names)
                count = len(new_unbound_names) - len(old_unbound_names)
                self.beginInsertRows(parent_index, pos, pos + count - 1)
                self._expressions[node_name] = new_expression
                self.endInsertRows()
            elif len(new_unbound_names) < len(old_unbound_names):
                pos = len(new_unbound_names)
                count = len(old_unbound_names) - len(new_unbound_names)
                self.beginRemoveRows(parent_index, pos, pos + count - 1)
                self._expressions[node_name] = new_expression
                self.endRemoveRows()
            else:
                self._expressions[node_name] = new_expression

            for i, (old_name, new_name) in enumerate(zip(old_unbound_names, new_unbound_names)):
                if old_name != new_name:
                    expression_index = self.index(i, 1, node_index)
                    self.dataChanged.emit(expression_index, expression_index, [Qt.ItemDataRole.DisplayRole])
            
            # emit expression changed
            self.dataChanged.emit(node_index, node_index, [role])
            return True
        
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        
        if index.isValid() and not index.parent().isValid():
            if index.column() == 0:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            elif index.column() == 1:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        elif index.isValid() and index.parent().isValid() and not index.parent().parent().isValid():
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # if insex

        # if IsNode:
        #     if index.column() == 0:
        #         return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        #     elif index.column() == 1:
        #         return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        # elif IsInlet or IsOutlet:
        #     return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if parent.isValid():
            # top-level: inserting nodes
            new_names = make_unique_id()
            return self.insertNodes(row, [new_names])
        else:
            # node level: inserting inlets/outlets is not allowed.
            warnings.warn("Inserting inlets/outlets is not supported.")
            return False

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        if count <= 0:
            return False

        parent_item = self.itemFromIndex(parent)
        if isinstance(parent_item, RootItem):
            if row < 0 or row + count > len(parent_item._nodes):
                return False
            self.beginRemoveRows(parent, row, row + count - 1)
            removed = parent_item._nodes[row:row + count]
            del parent_item._nodes[row:row + count]
            for node in removed:
                self._drop_node_cache(node)
                node._root.set(None)
            self.endRemoveRows()
            return True

        return False

