from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit, QGridLayout, QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

class DimensionSelectorDialog(QDialog):
    def __init__(self, dims, parent=None):
        """
        Parameters
        ----------
        dims: dict
            Maps dimension name (str) to list of possible values
        """
        super().__init__(parent)
        self.setWindowTitle("Select Dimension values")

        # maps dim name to widget (QComboBox or QLineEdit)
        self.inputs = {} 

        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.addWidget(QLabel("Dimension"), 0, 0)
        grid.addWidget(QLabel("Value"), 0, 1)

        for row, (d, vals) in enumerate(dims.items(), start=1):
            label = QLabel(d)
            grid.addWidget(label, row, 0)

            if 0 < len(vals) < 20:
                combo = QComboBox()
                combo.addItems([str(v) for v in vals])
                grid.addWidget(combo, row, 1)
                self.inputs[d] = combo
            else:
                line_edit = QLineEdit()
                line_edit.setPlaceholderText(f"Enter {d} value")
                grid.addWidget(line_edit, row, 1)
                self.inputs[d] = line_edit

        layout.addLayout(grid)

        # Add standard OK / Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_values(self):
        """
        Return a dict of dim_name -> selected/entered value as strings.
        """
        values = {}
        for dim_name, widget in self.inputs.items():
            if isinstance(widget, QComboBox):
                values[dim_name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                values[dim_name] = widget.text()
        return values

