from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit, QGridLayout, QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

class DimensionSelectorDialog(QDialog):
    def __init__(self, dims, dim_values_map, parent=None):
        """
        dims: list of dimension names (strings)
        dim_values_map: dict mapping dim name -> list/array of possible values
        """
        super().__init__(parent)
        self.setWindowTitle("Select Dimension Values")
        self.setModal(True)

        self.inputs = {}  # dim name -> widget (QComboBox or QLineEdit)

        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.addWidget(QLabel("Dimension"), 0, 0)
        grid.addWidget(QLabel("Value"), 0, 1)

        for row, dim_name in enumerate(dims, start=1):
            values = dim_values_map.get(dim_name, [])
            label = QLabel(dim_name)
            grid.addWidget(label, row, 0)

            if len(values) > 0 and len(values) < 20:
                combo = QComboBox()
                combo.addItems([str(v) for v in values])
                grid.addWidget(combo, row, 1)
                self.inputs[dim_name] = combo
            else:
                # large number of values, use free text input
                line_edit = QLineEdit()
                # Optional: set a placeholder
                line_edit.setPlaceholderText(f"Enter {dim_name} value")
                grid.addWidget(line_edit, row, 1)
                self.inputs[dim_name] = line_edit

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

