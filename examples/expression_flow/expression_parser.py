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
    QWidget,
    QLineEdit
)

class ExpressionWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.expression_input = QLineEdit()
        self.expression_input.textChanged.connect(self.on_expression_changed)
        self.output = QLabel("Output will be shown here")

        layout.addWidget(self.expression_input)
        layout.addWidget(self.output)
        self.setLayout(layout)

    def on_expression_changed(self, text: str):
        # Here you can add logic to evaluate the expression and update the output
        self.output.setText(f"Output: {text}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExpressionWidget()
    window.show()
    app.exec()