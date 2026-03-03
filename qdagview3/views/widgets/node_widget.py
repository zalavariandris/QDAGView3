from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from qdagview3.views.widgets.cell_widget import CellWidget
from qdagview3.views.widgets.port_widget import PortWidget
from qdagview3.views.utils.qt import distribute_items


class NodeWidget(QGraphicsItem):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # manage ports
        self._inlets: List[PortWidget] = []
        self._outlets: List[PortWidget] = []

        # manage cells
        self._header_cells: List[CellWidget] = []
        self._side_cells: List[CellWidget] = []

        self._graphview = None

    # manage inlets
    def _arrangeInlets(self, first=0, last=-1):
        for i, inlet in enumerate(self._inlets):
            inlet.setPos(0, -10)
        distribute_items(self._inlets, self.boundingRect().adjusted(10, 0, -10, 0), equal_spacing=False)

    def insertInlet(self, pos: int, inlet: PortWidget):
        self._inlets.insert(pos, inlet)
        inlet.setParentItem(self)
        self._arrangeInlets(pos)

    def removeInlet(self, inlet:PortWidget):
        self._inlets.remove(inlet)
        inlet.setParentItem(None)  # Remove from graphics hierarchy
        self._arrangeInlets()

    def inlets(self) -> list[PortWidget]:
        return [inlet for inlet in self._inlets]

    # manage outlets
    def _arrangeOutlets(self, first=0, last=-1):
        for i, outlet in enumerate(self._outlets):
            outlet.setPos(0, self.boundingRect().height() + 2)
        distribute_items(self._outlets, self.boundingRect().adjusted(10, 0, -10, 0), equal_spacing=False)

    def insertOutlet(self, pos: int, outlet: PortWidget):
        self._outlets.insert(pos, outlet)
        outlet.setParentItem(self)
        self._arrangeOutlets(pos)

    def removeOutlet(self, outlet: PortWidget):
        self._outlets.remove(outlet)
        outlet.setParentItem(None)  # Remove from graphics hierarchy
        self._arrangeOutlets()

    def outlets(self) -> list[PortWidget]:
        return [outlet for outlet in self._outlets]

    # manage central cells
    def _arrangeHeaderCells(self, first=0, last=-1):
        if len(self._header_cells) == 0:
            return

        for i, cell in enumerate(self._header_cells):
            cell.setPos(5, -2 + i * 12)  # First cell position
            cell.setTextWidth(self.boundingRect().width() - 10)

    def insertHeaderCell(self, pos, cell:CellWidget):
        self._header_cells.insert(pos, cell)
        cell.setParentItem(self)
        self._arrangeHeaderCells(pos)

    def removeHeaderCell(self, cell: CellWidget):
        self._header_cells.remove(cell)
        cell.setParentItem(None)  # Remove from graphics hierarchy
        self._arrangeHeaderCells()

    def headerCells(self) -> list[CellWidget]:
        return [cell for cell in self._header_cells]

    # manage side cells
    def _arrangeSideCells(self, first=0, last=-1):
        if len(self._side_cells) == 0:
            return

        for i, cell in enumerate(self._side_cells):
            cell.setPos(self.boundingRect().width(), -2 + i * 12)

    def insertSideCell(self, pos, cell:CellWidget):
        self._side_cells.insert(pos, cell)
        cell.setParentItem(self)
        self._arrangeSideCells(pos)

    def removeSideCell(self, cell: CellWidget):
        self._side_cells.remove(cell)
        cell.setParentItem(None)  # Remove from graphics hierarchy
        self._arrangeSideCells()

    def sideCells(self) -> list[CellWidget]:
        return [cell for cell in self._side_cells]

    # customize appearance
    def boundingRect(self):
        return QRectF(0, 0, 64*2, 20*2)
    
    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect
        
        palette = self.scene().palette()
        painter.setBrush(palette.alternateBase())
        if self.isSelected():
            painter.setBrush(palette.highlight())

        painter.drawRoundedRect(rect, 6, 6)



if __name__ == "__main__":
    app = QApplication([])
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    node = NodeWidget()

    scene.addItem(node)
    view.show()
    import sys
    sys.exit(app.exec())