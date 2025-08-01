import sys
import re
import pathlib
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QDialog
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
from PyQt6.QtCore import pyqtSignal
import platformdirs
import utils
import updates
import dimensions
import pandas as pd
import xarray as xr

from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QComboBox,
    QPushButton, QLineEdit
)
from PyQt6.QtCore import pyqtSignal

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit, QGridLayout, QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

class Model:
    def __init__(self):
        self.fn = None
        self.data = None        # pd.DataFrame or xr.Dataset
        self.vars = []          # list of strings
        self.v2d = {}           # maps variable to list of dimensions minus time
        self.d2vals = {}        # maps dim to list of possible values
        self.series = None      # the selected variable as a pd.Series
        self.var = None         # measuring this var
        self.dims = {}          # measuring var with these dims

    def read_fn(self, fn):

        self.series = None
        self.var = None
        self.dims = {}

        # get the data and set vars
        self.fn = fn
        if fn.suffix.lower() == ".csv":
            self.data = df = pd.read_csv(fn, index_col=0, parse_dates=[0])
            self.vars = df.columns.tolist()
            self.v2d = {v: [] for v in self.vars}
            self.d2vals = {}
        elif fn.suffix.lower() == ".nc":
            # unfortunately topnet doesn't write correct streamq files, time_bnd doesn't have attrs set
            #self.data = ds = xr.open_dataset(fn)
            self.data = ds = xr.open_dataset(fn, drop_variables="time_bnd")
            self.v2d = {
                v: [d for d in da.dims if not re.search(r"time|date", d, re.IGNORECASE)]
                for v, da in ds.data_vars.items()
                if any(re.search(r"time|date", d, re.IGNORECASE) for d in da.dims)
            }
            self.vars = sorted(self.v2d.keys())
            self.d2vals = {
                dim: ds.coords[dim].values.tolist()
                for dim in sorted(i for d in self.v2d.values() for i in d)
            }
        else:
            raise ValueError("Unsupported file format")

        if not self.vars:
            raise ValueError("No variables found in file")
        
        
    def get_vars(self):
        return self.vars

    def get_dims(self, v):
        """Return a dict from dim to possible values for given variable"""
        if v not in self.v2d:
            return {}
        return {d: self.d2vals[d] for d in sorted(self.v2d[v])}

    def set_var(self, v):
        self.series = None
        self.dims = {}
        # when clearing set_var gets called with None, so wipe it out
        if not v:
            self.var = None
            return

        if v not in self.vars:
            raise ValueError(f"Variable {v} does not exist in currently selected model file")

        self.var = v
        self.__set_series()

    def set_dims(self, d):
        """d is a dict of dim to value"""

        self.series = None
        if not d:
            self.dims = {}
            return

        self.dims = d
        self.__set_series()

    def __set_series(self):
        print("set_serioes", self.var, self.dims)
        if not self.var:
            return

        # no dimensions to worry about
        if not self.v2d[self.var]:
            self.series = self.data[self.var]
            return

        # we have dimensions to worry about, do we have them set?
        if self.dims and all(d in self.dims for d in self.v2d[self.var]):
            self.series = self.data[self.var].sel(self.dims).to_series()

        
class ModelWidget(QWidget):

    def __init__(self, model: Model, parent=None):
        super().__init__(parent)
        self.model = model
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        vbox = QVBoxLayout(self)

        # Title
        title = QLabel("Model output")
        vbox.addWidget(title)

        # Horizontal layout
        hbox = QHBoxLayout()

        # Model output file
        hbox.addWidget(QLabel("File:"))
        self.fn_le = lab = utils.ClickableLineEdit("Click to select file", char_width=15)
        lab.clicked.connect(self.select_model_file)
        hbox.addWidget(lab)

        # Variable label and dropdown
        hbox.addWidget(QLabel("Variable:"))
        self.vars_cb = cb = QComboBox()
        cb.currentTextChanged.connect(self.set_var)
        hbox.addWidget(cb)

        # Dimensions button
        self.dims_btn = btn = QPushButton("Dimensions")
        self.dims_btn.clicked.connect(self.set_dims)
        hbox.addWidget(btn)

        hbox.addStretch()

        # View button
        view_btn = QPushButton("View")
        hbox.addWidget(view_btn)

        vbox.addLayout(hbox)

    def select_model_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select a file", str(self.parent.get_lastdir()), "NetCDF or CSV Files (*.nc *.csv)")
        if not fname:
            return
        fname = pathlib.Path(fname)

        self.parent.set_lastdir(fname.parent)

        # update GUI
        self.fn_le.setText(fname.name)
        self.vars_cb.clear()
        self.dims_btn.setEnabled(fname.suffix.lower() == ".nc")

        # inform model about new file
        try:
            self.model.read_fn(fname)
            self.vars_cb.addItems(self.model.get_vars())
        except Exception as e:
            self.fn_le.setText("Click to select model")
            self.vars_cb.clear()
            self.dims_btn.setEnabled(False)
            QMessageBox.critical(self, "Error", f"Could not parse {fname}:\n{e}")

    def set_var(self, v):
        self.model.set_var(v)
    
    def set_dims(self):
        vname = self.vars_cb.currentText()
        if not vname:
            QMessageBox.warning(self, "No variable", "Please select a variable")
            return
        
        d2vals = self.model.get_dims(vname)
        if not d2vals:
            QMessageBox.warning(self, "No dims", f"There are no dimensions for {vname}")
            return


        dialog = DimensionSelectorDialog(d2vals, parent=self.parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_values = dialog.get_values()
            self.model.set_dims(selected_values)



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
                values[dim_name] = int(widget.currentText())        # FIXME, is it a float or int or str????
            elif isinstance(widget, QLineEdit):
                values[dim_name] = widget.text()
        return values

