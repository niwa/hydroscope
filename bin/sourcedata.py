import re
import pathlib
import json
import utils
import pandas as pd
import xarray as xr
import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
)


class SourceData:
    def __init__(self):
        self.fn = None
        self.data = None  # pd.DataFrame or xr.Dataset
        self.vars = []  # list of strings
        self.v2d = {}  # maps variable to list of dimensions minus time
        self.v2u = {}  # maps variable to unit (possibly None, for csv will be None)
        self.d2vals = {}  # maps dim to list of possible values
        self.d2type = {}  # maps dim to the type of values
        self.series = None  # the selected variable as a pd.Series
        self.units = None  # the units of selected variable as a string
        self.var = None  # measuring this var
        self.dims = {}  # measuring var with these dims

    def read_fn(self, fn):

        self.series = None
        self.var = None
        self.dims = {}

        # get the data and set vars
        self.fn = fn
        if fn.suffix.lower() == ".csv":
            try:
                df = pd.read_csv(fn, index_col=0, parse_dates=[0])
                df.index = pd.to_datetime(df.index, errors="raise")
            except Exception as exp1:
                # lets try and recover by assuming DD/MM/YYYY format
                try:
                    df = pd.read_csv(fn, index_col=0, parse_dates=[0])
                    df.index = pd.to_datetime(df.index, dayfirst=True, errors="raise")
                except Exception as exp2:
                    raise ValueError(
                        f"Unsupported file format, please read Help menu.\nOriginal error:\n{exp1}\nFallback error assuming DD/MM/YYYY:\n{exp2}"
                    )
            if pd.infer_freq(df.index) is None:
                raise ValueError(f"First column doesn't have uniform frequency")
            self.vars = df.columns.tolist()
            try:
                df.apply(pd.to_numeric, errors="raise")
            except Exception as exp:
                raise ValueError("All defined values must be numeric")
            self.data = df
            self.v2d = {v: [] for v in self.vars}
            self.v2u = {v: None for v in self.vars}
            self.d2vals = {}
        elif fn.suffix.lower() == ".nc":
            # unfortunately topnet doesn't write correct streamq files, time_bnd doesn't have attrs set
            # self.data = ds = xr.open_dataset(fn)
            self.data = ds = xr.open_dataset(fn, drop_variables="time_bnd")
            self.v2d = {
                v: [d for d in da.dims if not re.search(r"time|date", d, re.IGNORECASE)]
                for v, da in ds.data_vars.items()
                if any(re.search(r"time|date", d, re.IGNORECASE) for d in da.dims)
            }
            self.vars = sorted(self.v2d.keys())
            self.v2u = {v: ds.data_vars[v].attrs.get("units", None) for v in self.vars}
            self.d2vals = {
                dim: ds.coords[dim].values.tolist()
                for dim in sorted(i for d in self.v2d.values() for i in d)
            }
            self.d2type = {d: type(v[0]) for d, v in self.d2vals.items()}
        else:
            raise ValueError("Unsupported file format")

        if not self.vars or len(self.vars) < 1:
            raise ValueError("No variables found in file")

    def get_vars(self):
        return self.vars

    def get_dims(self):
        return self.dims

    def get_d2type(self):
        return self.d2type

    def get_d2vals(self, v):
        """Return a dict from dim to possible values for given variable"""
        if v not in self.v2d:
            return {}
        return {d: self.d2vals[d] for d in sorted(self.v2d[v])}

    def set_var(self, v):
        self.series = None
        self.dims = {}
        self.units = None

        # when clearing set_var gets called with None, so wipe it out
        if not v:
            self.var = None
            return

        if v not in self.vars:
            raise ValueError(f"Variable {v} does not exist in currently selected file")

        self.var = v
        self.__set_series(update_units=True)

    def set_dims(self, d):
        """d is a dict of dim to value"""

        self.series = None
        if not d:
            self.dims = {}
            return

        self.dims = d
        self.__set_series()

    def __set_series(self, update_units=False):
        if not self.var:
            return

        if update_units:
            self.set_units(self.v2u.get(self.var, None))

        # no dimensions to worry about
        if not self.v2d[self.var]:
            self.series = self.data[self.var]
            return

        # we have dimensions to worry about, do we have them set?
        if self.dims and all(d in self.dims for d in self.v2d[self.var]):
            self.series = self.data[self.var].sel(self.dims).to_series()

    def get_series(self):
        return self.series

    def set_units(self, u):
        self.units = u

    def get_units(self):
        return self.units


class SourceDataWidget(QGroupBox):

    def __init__(self, sd: SourceData, title="Model", parent=None):
        super().__init__(title, parent=parent)
        self.sd = sd
        self.title = title
        self.parent = parent
        self.init_ui()

        # if we had a previous file, load it
        fname = self.parent.cp["DEFAULT"].get(f"{self.title}_fname")
        if fname and (fname := pathlib.Path(fname)) and fname.exists():
            self.__set_sourcedata_file(fname)

        # if there is a var saved, lets set it
        v = self.parent.cp["DEFAULT"].get(f"{self.title}_var")
        if v and v in self.sd.get_vars() and self.vars_cb.findText(v) != -1:
            self.vars_cb.setCurrentText(v)

        # units
        if u := self.parent.cp["DEFAULT"].get(f"{self.title}_units"):
            self.units_le.setText(u)

    def init_ui(self):

        # Horizontal layout
        hbox = QHBoxLayout(self)

        # Model/obs output file
        hbox.addWidget(QLabel("File:"))
        self.fn_le = lab = utils.ClickableLineEdit("Click to select file", char_width=15)
        lab.setMinimumWidth(100)
        lab.clicked.connect(self.__act_sourcedata_file)  # user change, so store in config
        hbox.addWidget(lab)

        # Variable label and dropdown
        hbox.addWidget(QLabel("Variable:"))
        self.vars_cb = cb = QComboBox()
        cb.setMinimumWidth(100)
        cb.currentTextChanged.connect(
            self.__set_var
        )  # programmatically set, so dont store in config
        cb.activated.connect(self.__act_var)  # when user changes it we store in config
        hbox.addWidget(cb)

        # Units
        hbox.addWidget(QLabel("Units:"))
        self.units_le = le = QLineEdit()
        le.setMaximumWidth(80)
        le.textChanged.connect(self.__set_units)  # programmatically set, so dont store in config
        le.textEdited.connect(self.__act_units)  # only when user changes we store
        hbox.addWidget(le)

        # Dimensions button
        self.dims_btn = btn = QPushButton("Dimensions")
        self.dims_btn.clicked.connect(self.set_dims)
        hbox.addWidget(btn)

        hbox.addStretch()

        # View button
        view_btn = QPushButton("View")
        view_btn.clicked.connect(self.view_series)
        hbox.addWidget(view_btn)

    def __act_sourcedata_file(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            self.parent.cp["DEFAULT"]["lastdir"],
            "NetCDF or CSV Files (*.nc *.csv)",
        )
        if not fname:
            return
        fname = pathlib.Path(fname)

        self.parent.cp["DEFAULT"]["lastdir"] = str(fname.parent)

        # store fname
        self.parent.cp["DEFAULT"][f"{self.title}_fname"] = str(fname)
        self.parent.save_config()

        self.__set_sourcedata_file(fname)

    def __set_sourcedata_file(self, fname: pathlib.Path):
        self.fn_le.setText(fname.name)
        self.vars_cb.clear()
        self.dims_btn.setEnabled(fname.suffix.lower() == ".nc")

        # inform model/obs about new file
        try:
            self.sd.read_fn(fname)
            self.vars_cb.addItems(self.sd.get_vars())
        except Exception as e:
            self.fn_le.setText("Click to select file")
            self.vars_cb.clear()
            self.dims_btn.setEnabled(False)
            QMessageBox.critical(self, "Error", f"Could not parse {fname}:\n{e}")

    def view_series(self):
        s = self.sd.get_series()
        if s is None:
            QMessageBox.warning(self, "No variable", "File/variable/dimension must be all set")
            return

        class PlotDialog(QDialog):
            def __init__(self, parent, series):
                super().__init__(parent)
                self.setWindowTitle("Series Plot")

                layout = QVBoxLayout(self)

                # dim string
                dims = parent.sd.get_dims()
                if dims:
                    dstr = [f"{dim}={val}" for dim, val in dims.items()]
                    dstr = f" ({','.join(dstr)})"
                else:
                    dstr = ""

                # Create Matplotlib Figure
                fig, ax = plt.subplots()
                series.plot(ax=ax)
                ax.set_title(f"{parent.sd.var}{dstr}")
                ax.set_xlabel("Time")

                # if there is a name, use it
                lab = series.name if series.name else "Value"
                if u := parent.sd.get_units():
                    lab = f"{lab} ({u})"
                ax.set_ylabel(lab)

                fig.tight_layout()

                canvas = FigureCanvas(fig)
                layout.addWidget(canvas)

                b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
                b.accepted.connect(self.accept)
                layout.addWidget(b)

        d = PlotDialog(self, s)
        d.exec()

    def __set_var(self, v):
        self.sd.set_var(v)
        self.units_le.setText(self.sd.get_units())

    def __act_var(self, idx):
        """When user changes var we save it"""
        self.parent.cp["DEFAULT"][f"{self.title}_var"] = self.vars_cb.itemText(idx)
        self.__set_var(self.vars_cb.itemText(idx))

    def __set_units(self, u):
        self.sd.set_units(u)

    def __act_units(self, u):
        self.parent.cp["DEFAULT"][f"{self.title}_units"] = u

    def set_dims(self):
        vname = self.vars_cb.currentText()
        if not vname:
            QMessageBox.warning(self, "No variable", "Please select a variable")
            return

        d2vals = self.sd.get_d2vals(vname)
        if not d2vals:
            QMessageBox.warning(self, "No dims", f"There are no dimensions for {vname}")
            return

        dialog = DimensionSelectorDialog(
            d2vals, self.sd.get_d2type(), self.sd.get_dims(), parent=self.parent
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_values = dialog.get_values()
            self.parent.cp["DEFAULT"][f"{self.title}_dims"] = json.dumps(selected_values)
            self.sd.set_dims(selected_values)


class DimensionSelectorDialog(QDialog):
    def __init__(self, d2vals, d2type, dims, parent=None):
        """
        Parameters
        ----------
        d2vals: dict
            Maps dimension name (str) to list of possible values
        d2type: dict
            Maps dimension name (str) to type of the values
        dims: dict
            Maps dimension name (str) to values.  This maybe empty if no dims currently set (this is to set the default)

        """
        super().__init__(parent)
        self.setWindowTitle("Select Dimension values")

        # maps dim name to widget (QComboBox or QLineEdit)
        self.inputs = {}

        # maps dim name to the type of the values
        self.d2type = d2type

        # need to set up buttons now because if line_edit is used then disable Ok button until input
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(True)

        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.addWidget(QLabel("Dimension"), 0, 0)
        grid.addWidget(QLabel("Value"), 0, 1)

        for row, (d, vals) in enumerate(d2vals.items(), start=1):
            label = QLabel(d)
            grid.addWidget(label, row, 0)

            if 0 < len(vals) < 20:
                combo = QComboBox()
                combo.addItems([str(v) for v in vals])
                if dims and d in dims:
                    combo.setCurrentText(str(dims[d]))
                grid.addWidget(combo, row, 1)
                self.inputs[d] = combo
            else:
                line_edit = QLineEdit()
                line_edit.setPlaceholderText(f"Enter {d} value")
                line_edit.setValidator(
                    QRegularExpressionValidator(
                        QRegularExpression(f"^({'|'.join(map(str, vals))})$")
                    )
                )
                grid.addWidget(line_edit, row, 1)
                self.inputs[d] = line_edit
                line_edit.textChanged.connect(
                    lambda _: ok_button.setEnabled(
                        bool(line_edit.text().strip()) and line_edit.hasAcceptableInput()
                    )
                )
                ok_button.setEnabled(False)

        layout.addLayout(grid)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_values(self):
        """
        Return a dict of dim_name -> selected/entered value as strings.
        """
        vals = {}
        for dim, widget in self.inputs.items():
            v = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
            vals[dim] = self.d2type[dim](v)
        return vals
