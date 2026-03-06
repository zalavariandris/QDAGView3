from __future__ import annotations

import sys
from typing import List

from qtpy.QtCore import (
    QModelIndex, 
    Qt, 
    QItemSelection, 
    QItemSelectionModel
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableView,
    QToolBar,
    QTreeView,
    QListView,
    QWidget
)

from qdagview3.models.link_model import LinkModel
# from qdagview3.models.socket_based_nodes_model import SocketBasedNodesModel

from qdagview3.views.graph_view import GraphView

from expression_model import ExpressionsModel
from expression_delegate import ExpressionGraphDelegate, GraphRole, GraphDataRole
from expression_inspector import ExpressionInspector

# class ExpressionInspector(QWidget):
#     def __init__(self, parent: QWidget | None = None):
#         super().__init__(parent)
#         layout = QVBoxLayout(self)
#         self.title_label = QLabel("Select a node or link to see details", self)
#         layout.addWidget(self.title_label)

class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tree Model Editor")
        self.resize(960, 600)

        # - model -
        self.nodes_model = ExpressionsModel(self)
        self.nodes_selection_model = QItemSelectionModel(self.nodes_model, self)
        self.link_model = LinkModel(self.nodes_model, self)
        self.link_selection_model = QItemSelectionModel(self.link_model, self)

        # - populate with some initial data -

        self.nodes_model.insertNodes(0, ["Node1", "Node2"])
        n1 = self.nodes_model.index(0, 0, QModelIndex())
        n2 = self.nodes_model.index(1, 0, QModelIndex())
        assert n1.isValid() and n2.isValid(), "Failed to create initial nodes"
        outlet = self.nodes_model.outlets(n1)[0]
        # inlet = self.nodes_model.inlets(n2)[0]
        # assert outlet.isValid() and inlet.isValid(), "Failed to create initial nodes with inlets/outlets"
        # self.link_model.add_link(outlet, inlet)
        
        # - graph view -
        delegate = ExpressionGraphDelegate()
        self.graph_view = GraphView(delegate=delegate, parent=self)
        self.graph_view.setModel(self.link_model)
        self.graph_view.setNodesSelectionModel(self.nodes_selection_model)
        self.graph_view.setLinksSelectionModel(self.link_selection_model)

        # - nodes list -
        self.nodes_table = QTableView(self)
        self.nodes_table.setModel(self.nodes_model)
        self.nodes_table.setSelectionModel(self.nodes_selection_model)
        # self.nodes_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        # self.nodes_list.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # self.nodes_table.setFixedWidth(200)
        # self.nodes_table.verticalHeader().setVisible(True)
        # self.nodes_table.verticalHeader().setFixedWidth(100)
        # self.nodes_list.setHeaderHidden(False)

        # - inspector -
        self.inspector = ExpressionInspector(self.nodes_model, self)
        self.nodes_selection_model.currentChanged.connect(lambda current, previous: self.inspector.show_row(current.row()))

        # - actions -
        toolbar = QToolBar("Actions", self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.addAction("Add Node", self.add_expression)
        toolbar.addAction("Link Selected", self.link_selected)
        toolbar.addAction("Remove Selected", self.remove_selected)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.nodes_table, 0)
        layout.addWidget(self.graph_view, 1)
        layout.addWidget(self.inspector, 0)

        self.setCentralWidget(central)

    def add_expression(self, name: str|None=None) -> QModelIndex|None:
        ...
        nodes_count = self.nodes_model.rowCount(QModelIndex())
        import re
        from typing import Iterable
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
        all_nodes_names = [self.nodes_model.data(self.nodes_model.index(row, 0, QModelIndex()), Qt.DisplayRole) for row in range(nodes_count)]
        unique_name = make_unique_name(name or "NewNode", all_nodes_names)
        self.nodes_model.insertNodes(nodes_count, [unique_name])
        # row_count = self.nodes_model.rowCount(QModelIndex())
        # self.nodes_model.appendNode(name or f"Node{row_count + 1}")
        # node_index = self.nodes_model.index(row_count, 0, QModelIndex())
        # self.nodes_model.appendInlet(node_index, "In")
        # self.nodes_model.appendOutlet(node_index, "Out")
        # return self.nodes_model.index(row_count, 0, QModelIndex())

    def link_selected(self) -> None:
        selected_rows = self.nodes_selection_model.selectedRows()
        if len(selected_rows) != 2:
            QMessageBox.information(self, "Link Nodes", "Select exactly two nodes to link.")
            return

        source_index, target_index = selected_rows


        if (self.graph_view._delegate.canAcceptLink(source_index, target_index) 
            and self.link_model.add_link(source_index, target_index)):
            self.link_selection_model.setCurrentIndex(
                self.link_model.index(self.link_model.rowCount(QModelIndex()) - 1, 0, QModelIndex()),
                QItemSelectionModel.SelectionFlag.SelectCurrent
            )
        else:
            QMessageBox.warning(self, "Link Nodes", "Failed to link the selected nodes.")

    def remove_selected(self) -> None:
        self._remove_selected_links()
        self._remove_selected_nodes()

    def _remove_selected_nodes(self) -> None:
        def get_roots(selected_indexes) -> List[QModelIndex]:
            row_roots_by_item_id = {}
            for index in selected_indexes:
                row_root = index.sibling(index.row(), 0)
                row_roots_by_item_id[id(row_root.internalPointer())] = row_root
            return list(row_roots_by_item_id.values())
        
        selected_rows = get_roots(self.nodes_selection_model.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "Remove Item", "Select one or more items to remove.")
            return

        selected_item_ids = {id(index.internalPointer()) for index in selected_rows}

        def has_selected_ancestor(index: QModelIndex) -> bool:
            parent = index.parent()
            while parent.isValid():
                if id(parent.internalPointer()) in selected_item_ids:
                    return True
                parent = parent.parent()
            return False

        roots = [index for index in selected_rows if not has_selected_ancestor(index)]

        def depth(index: QModelIndex) -> int:
            d = 0
            parent = index.parent()
            while parent.isValid():
                d += 1
                parent = parent.parent()
            return d

        roots.sort(key=lambda index: (depth(index), index.row()), reverse=True)
        for index in roots:
            self.nodes_model.removeRows(index.row(), 1, index.parent())

    def _remove_selected_links(self) -> None:
        selected_rows = [index.row() for index in self.link_selection_model.selectedRows()]
        if not selected_rows:
            QMessageBox.information(self, "Remove Link", "Select one or more links to remove.")
            return

        self.link_model.remove_links(sorted(set(selected_rows)))

def main():
    print("Starting application...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
