from __future__ import annotations

import sys
from typing import List

from qtpy.QtCore import QModelIndex, Qt
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
    QVBoxLayout,
    QWidget,
)

from qdagview3.models.link_model import LinkModel
from qdagview3.models.standard_nodes_model import StandardNodesModel

from qdagview3.views.graph_view import GraphView
from qdagview3.views.delegates.tree_graph_delegate import TreeGraphDelegate


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tree Model Editor")
        self.resize(960, 600)

        # - model -
        self.nodes_model = StandardNodesModel(self)
        self.link_model = LinkModel(self.nodes_model, self)
        self.nodes_model.insertRows(0, 2, QModelIndex())
        node1 = self.nodes_model.index(0, 0, QModelIndex())
        self.nodes_model.setData(node1, "Node 1", Qt.EditRole)
        self.nodes_model.insertRows(0, 1, node1)
        outlet = self.nodes_model.index(0, 0, node1)
        self.nodes_model.setData(outlet, "Outlet", Qt.EditRole)
        node2 = self.nodes_model.index(1, 0, QModelIndex())
        self.nodes_model.insertRows(0, 1, node2)
        inlet = self.nodes_model.index(0, 0, node2)
        self.nodes_model.setData(inlet, "Inlet", Qt.EditRole)
        self.nodes_model.setData(node2, "Node 2", Qt.EditRole)
        self.link_model.add_link(outlet, node2)
        

        delegate = TreeGraphDelegate()
        self.graph_view = GraphView(delegate=delegate, parent=self)
        self.graph_view.setModel(self.link_model)

        # - node tree views -
        self.node_tree_view = QTreeView(self)
        self.node_tree_view.setModel(self.nodes_model)
        self.node_tree_view.setAlternatingRowColors(True)
        self.node_tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.node_tree_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.node_tree_view.setEditTriggers(
            QTreeView.DoubleClicked
            | QTreeView.SelectedClicked
            | QTreeView.EditKeyPressed
        )
        self.node_tree_view.header().setSectionResizeMode(QHeaderView.Stretch)
        self.node_tree_view.selectionModel().currentChanged.connect(self.sync_subtree_root)

        self.node_subtree_view = QTreeView(self)
        self.node_subtree_view.setModel(self.nodes_model)
        self.node_subtree_view.setAlternatingRowColors(True)
        self.node_subtree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.node_subtree_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.node_subtree_view.setEditTriggers(
            QTreeView.DoubleClicked
            | QTreeView.SelectedClicked
            | QTreeView.EditKeyPressed
        )
        self.node_subtree_view.header().setSectionResizeMode(QHeaderView.Stretch)
        self.node_tree_view.header().sectionResized.connect(self.sync_column_width_to_subtree)

        # - link view -
        self.link_view = QTableView(self)
        self.link_view.setModel(self.link_model)
        self.link_view.setAlternatingRowColors(True)
        self.link_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.link_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.link_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.link_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.link_model.setNodesModel(self.nodes_model)

        # - actions -
        toolbar = QToolBar("Actions", self)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        toolbar.addAction("Add Root Item", self.add_root_item)
        toolbar.addAction("Add Child Item", self.add_child_item)
        toolbar.addAction("Remove Selected Items", self.remove_selected_items)
        toolbar.addSeparator()
        toolbar.addAction("Create Link From Selection", self.create_link_from_selection)
        toolbar.addAction("Remove Selected Links", self.remove_selected_links)
        toolbar.addSeparator()
        toolbar.addAction("Add Column", self.add_column)
        toolbar.addAction("Remove Column", self.remove_column)
        toolbar.addAction("Rename Current Column", self.rename_current_column)

        central = QWidget()
        layout = QHBoxLayout(central)
        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.addWidget(QLabel("Main Tree"))
        tree_layout.addWidget(self.node_tree_view, 2)
        tree_layout.addWidget(QLabel("Current Subtree"))
        tree_layout.addWidget(self.node_subtree_view, 1)

        link_panel = QWidget()
        link_layout = QVBoxLayout(link_panel)
        link_layout.addWidget(QLabel("Links"))
        link_layout.addWidget(self.link_view)

        layout.addWidget(tree_panel, 2)
        layout.addWidget(link_panel, 1)
        layout.addWidget(self.graph_view, 3)
        self.setCentralWidget(central)

        self.node_tree_view.expandAll()
        self.node_subtree_view.expandAll()

    def selected_index(self) -> QModelIndex:
        index = self.node_tree_view.currentIndex()
        if index.isValid():
            return index
        return QModelIndex()

    def selected_row_roots(self) -> List[QModelIndex]:
        selection_model = self.node_tree_view.selectionModel()
        selected_indexes = selection_model.selectedIndexes()
        row_roots_by_item_id = {}
        for index in selected_indexes:
            row_root = index.sibling(index.row(), 0)
            row_roots_by_item_id[id(row_root.internalPointer())] = row_root
        return list(row_roots_by_item_id.values())

    def sync_subtree_root(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        if not current.isValid():
            self.node_subtree_view.setRootIndex(QModelIndex())
            return

        root = current.sibling(current.row(), 0)
        self.node_subtree_view.setRootIndex(root)
        self.node_subtree_view.expandAll()

    def sync_column_width_to_subtree(self, logical_index: int, old_size: int, new_size: int) -> None:
        del old_size
        self.node_subtree_view.header().resizeSection(logical_index, new_size)

    def add_root_item(self) -> None:
        row = self.nodes_model.rowCount(QModelIndex())
        if not self.nodes_model.insertRows(row, 1, QModelIndex()):
            return
        index = self.nodes_model.index(row, 0, QModelIndex())
        self.node_tree_view.expandAll()
        self.node_tree_view.setCurrentIndex(index)

    def add_child_item(self) -> None:
        parent_index = self.selected_index()
        if parent_index.isValid():
            parent_index = parent_index.sibling(parent_index.row(), 0)
        row = self.nodes_model.rowCount(parent_index)
        if not self.nodes_model.insertRows(row, 1, parent_index):
            return
        self.node_tree_view.expand(parent_index)

    def remove_selected_items(self) -> None:
        selected_rows = self.selected_row_roots()
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

    def create_link_from_selection(self) -> None:
        selected_rows = self.selected_row_roots()
        if len(selected_rows) != 2:
            QMessageBox.information(
                self,
                "Create Link",
                "Select exactly two tree items to create one link.",
            )
            return

        source, target = selected_rows
        created_row = self.link_model.add_link(source, target)
        if created_row < 0:
            QMessageBox.warning(
                self,
                "Create Link",
                "Could not create link: source/target are not valid indexes from the tree model.",
            )

    def remove_selected_links(self) -> None:
        selection_model = self.link_view.selectionModel()
        selected_rows = [index.row() for index in selection_model.selectedRows()]
        if not selected_rows:
            QMessageBox.information(self, "Remove Link", "Select one or more links to remove.")
            return

        for row in sorted(set(selected_rows), reverse=True):
            self.link_model.remove_link(row)

    def add_column(self) -> None:
        default_name = f"Column {self.nodes_model.columnCount() + 1}"
        header, ok = QInputDialog.getText(
            self,
            "Add Column",
            "New column name:",
            text=default_name,
        )
        if not ok:
            return

        header = header.strip() or default_name
        new_col = self.nodes_model.columnCount()
        if not self.nodes_model.insertColumns(new_col, 1, QModelIndex()):
            return
        self.nodes_model.setHeaderData(new_col, Qt.Horizontal, header, Qt.EditRole)
        self.node_tree_view.header().setSectionResizeMode(new_col, QHeaderView.Stretch)
        self.node_subtree_view.header().setSectionResizeMode(new_col, QHeaderView.Stretch)

    def remove_column(self) -> None:
        if self.nodes_model.columnCount() <= 1:
            QMessageBox.warning(self, "Remove Column", "At least one column must remain.")
            return

        max_index = self.nodes_model.columnCount() - 1
        value, ok = QInputDialog.getInt(
            self,
            "Remove Column",
            "Column index to remove (0-based):",
            value=max_index,
            min=0,
            max=max_index,
        )
        if not ok:
            return

        removed = self.nodes_model.removeColumns(value, 1, QModelIndex())
        if not removed:
            QMessageBox.warning(self, "Remove Column", "Invalid column index.")

    def rename_current_column(self) -> None:
        current = self.node_tree_view.currentIndex()
        if not current.isValid():
            QMessageBox.information(self, "Rename Column", "Set a current cell first.")
            return

        column = current.column()
        old_name = self.nodes_model.headerData(column, Qt.Horizontal, Qt.DisplayRole) or f"Column {column + 1}"
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Current Column",
            f"New name for column {column}:",
            text=str(old_name),
        )
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Rename Column", "Column name cannot be empty.")
            return

        self.nodes_model.setHeaderData(column, Qt.Horizontal, new_name, Qt.EditRole)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
