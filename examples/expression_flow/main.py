from __future__ import annotations

import sys
from typing import List

from qtpy.QtCore import QModelIndex, Qt, QItemSelection, QItemSelectionModel
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableView,
    QToolBar,
    QTreeView,
    QListView,
    QVBoxLayout,
    QWidget
)

from qdagview3.models.link_model import LinkModel
from qdagview3.models.socket_based_nodes_model import SocketBasedNodesModel

from qdagview3.views.graph_view import GraphView
from qdagview3.delegates.tree_graph_delegate import TreeGraphDelegate


from expression_delegate import ExpressionGraphDelegate, GraphRole, GraphDataRole


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tree Model Editor")
        self.resize(960, 600)

        # - model -
        self.nodes_model = SocketBasedNodesModel(self)
        self.nodes_selection_model = QItemSelectionModel(self.nodes_model, self)
        self.link_model = LinkModel(self.nodes_model, self)
        self.link_selection_model = QItemSelectionModel(self.link_model, self)

        # - populate with some initial data -
        n1 = self.add_node("Node1")
        n2 = self.add_node("Node2")
        outlet = self.nodes_model.index(1, 0, n1)
        inlet = self.nodes_model.index(0, 0, n2)
        self.link_model.add_link(outlet, inlet)
        
        # - graph view -
        delegate = ExpressionGraphDelegate()
        self.graph_view = GraphView(delegate=delegate, parent=self)
        self.graph_view.setModel(self.link_model)
        self.graph_view.setNodesSelectionModel(self.nodes_selection_model)
        self.graph_view.setLinksSelectionModel(self.link_selection_model)

        # - nodes list -
        self.nodes_table = QListView(self)
        self.nodes_table.setModel(self.nodes_model)
        self.nodes_table.setSelectionModel(self.nodes_selection_model)
        # self.nodes_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        # self.nodes_list.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # self.nodes_table.setFixedWidth(200)
        # self.nodes_table.verticalHeader().setVisible(True)
        # self.nodes_table.verticalHeader().setFixedWidth(100)
        # self.nodes_list.setHeaderHidden(False)

        # - actions -
        toolbar = QToolBar("Actions", self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.addAction("Add Node", self.add_node)
        toolbar.addAction("Link Selected", self.link_selected)
        toolbar.addAction("Remove Selected", self.remove_selected)

        central = QWidget()
        layout = QHBoxLayout(central)

        layout.addWidget(self.graph_view, 1)
        layout.addWidget(self.nodes_table, 0)
        self.setCentralWidget(central)

    def add_node(self, name: str|None=None) -> QModelIndex|None:
        row_count = self.nodes_model.rowCount(QModelIndex())
        self.nodes_model.appendNode(name or f"Node{row_count + 1}")
        node_index = self.nodes_model.index(row_count, 0, QModelIndex())
        self.nodes_model.appendInlet(node_index, "In")
        self.nodes_model.appendOutlet(node_index, "Out")
        return self.nodes_model.index(row_count, 0, QModelIndex())

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

def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
