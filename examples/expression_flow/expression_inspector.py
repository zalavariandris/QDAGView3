
from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex, 
    Qt, 
    QItemSelection, 
    QItemSelectionModel
)

from qtpy.QtWidgets import (
    QFrame,
    QLineEdit,
    QFormLayout,
    QDataWidgetMapper,
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

class ExpressionInspector(QWidget):
    """
    Shows and edits fields for the currently selected row via QDataWidgetMapper.
    Column-to-field mapping is driven by the model's horizontal headers.
    """

    def __init__(self, model: QAbstractItemModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._fields: dict[str, QLineEdit] = {}

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        form = QFormLayout(frame)

        # Build one QLineEdit per column, keyed by header label
        for col in range(model.columnCount()):
            label = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            edit  = QLineEdit()
            form   .addRow(f"{label}:", edit)
            self._fields[label] = edit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)

        self.tree = QTreeView()
        self.tree.setModel(model)
        layout.addWidget(self.tree)

        # Mapper
        self.mapper = QDataWidgetMapper(self)
        self.mapper.setModel(model)
        for col, edit in enumerate(self._fields.values()):
            self.mapper.addMapping(edit, col)

        self.mapper.setSubmitPolicy(QDataWidgetMapper.SubmitPolicy.AutoSubmit)
        self.mapper.toFirst()

    def show_row(self, row: int):
        if row < 0:
            # self.mapper.clearMapping()
            for edit in self._fields.values():
                edit.clear()

            self.tree.setModel(None)
        else:
            print("Showing row", row)
            self.mapper.setCurrentIndex(row)
            self.tree.setModel(self._model)
            self.tree.setRootIndex(self._model.index(row, 0, QModelIndex()))