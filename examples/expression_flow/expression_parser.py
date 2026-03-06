from __future__ import annotations

import sys
from typing import List

from qtpy.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QLabel,
    QWidget,
    QLineEdit
)

from qdagview3.evaluate_python import find_unbounded_names, format_exception

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
        try:
            unbounded_names = find_unbounded_names(text)
            if unbounded_names:
                variables = list(filter(lambda name: str(name) not in dir(__builtins__), unbounded_names))
                self.output.setText(f"Unbounded names: {', '.join(variables)}")
            else:
                self.output.setText(f"Output: {text}")
        except Exception as e:
            self.output.setText(f"Error: {format_exception(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExpressionWidget()
    window.show()
    app.exec()