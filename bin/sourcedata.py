import re
import pathlib
import json
import utils
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtGui import QRegularExpressionValidator, QFontDatabase, QDoubleValidator, QFont
from PyQt6.QtCore import QRegularExpression, QDateTime, Qt
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
    QDateTimeEdit,
    QPlainTextEdit,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QFormLayout,
    QSpacerItem,
)


class SourceData:
    def __init__(self):
        self.fn = None
        self.data = None  # pd.DataFrame or xr.Dataset
        self.vars = []  # list of strings of variable names in self.data
        self.v2d = {}  # maps variable to list of dimensions minus time in self.data
        self.v2u = {}  # maps variable to unit (possibly None, for csv will be None) in self.data
        self.d2vals = {}  # maps dim to list of possible values in self.data
        self.d2type = {}  # maps dim to the type of values in self.data

        # these are for selected variable
        self.series = None  # the selected variable as a pd.Series
        self.units = None  # the units of selected variable as a string
        self.var = None  # measuring this var
        self.agg = "mean"  # aggregation method as a string (mean, sum, max, min)
        self.dims = {}  # measuring var with these dims
        self.timerange = [None, None]  # possibly restrict time range to this for this var

    def read_fn(self, fn, guessnodata: bool):

        self.series = None
        self.units = None
        self.var = None
        self.agg = "mean"
        self.dims = {}
        self.timerange = [None, None]

        # if we shouldn't show the guessnodata dialog again
        never_show_guessnodata = False

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
                raise ValueError("First column doesn't have uniform frequency")
            df.index.name = 'time'
            if guessnodata:
                dlg = GuessNoDataDialog(df)
                if dlg.var2guess and dlg.exec():
                    never_show_guessnodata = dlg.never_show.isChecked()
                    for var, val in dlg.var2nodata.items():
                        df.loc[df[var]==val, var] = np.nan
            self.vars = df.columns.tolist()
            try:
                df.apply(pd.to_numeric, errors="raise")
            except Exception:
                raise ValueError("All defined values must be numeric")
            df["time"] = df.index
            self.data = df
            self.v2d = {v: [] for v in self.vars}
            self.v2u = {v: None for v in self.vars}
            self.d2vals = {}
        elif fn.suffix.lower() == ".nc":
            # unfortunately topnet doesn't write correct streamq files, time_bnd doesn't have attrs set
            # self.data = ds = xr.open_dataset(fn)
            self.data = ds = xr.open_dataset(fn, drop_variables="time_bnd")
            # rename and time like dim or coord to time
            for dim in ds.dims:
                if dim.lower() in ("time", "date", "datetime"):
                    if dim != "time":
                        ds = ds.rename({dim: "time"})
            for coord in ds.coords:
                if coord.lower() in ("time", "date", "datetime"):
                    if coord != "time":
                        ds = ds.rename({coord: "time"})
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

        # if we were guessing, but shouldn't, return True
        return guessnodata and never_show_guessnodata

    def get_vars(self):
        return self.vars

    def get_d2type(self):
        return self.d2type

    def get_d2vals(self, v):
        """Return a dict from dim to possible values for given variable"""
        if v not in self.v2d:
            return {}
        return {d: self.d2vals[d] for d in sorted(self.v2d[v])}

    def set_var(self, v):
        self.series = None
        self.units = None
        self.dims = {}
        self.timerange = [None, None]

        # when clearing set_var gets called with None, so wipe it out
        if not v:
            self.var = None
            return

        if v not in self.vars:
            raise ValueError(f"Variable {v} does not exist in currently selected file")

        self.var = v
        self.__set_series(update_units=True)

    def get_dims(self):
        return self.dims

    def set_dims(self, d2v):
        """d2v is a dict of dim to value"""

        self.series = None
        if not d2v:
            self.dims = {}
            return

        if not all([d in self.d2vals and v in self.d2vals[d] for d, v in d2v.items()]):
            return

        self.dims = d2v
        self.__set_series()

    def get_timerange(self):
        return self.timerange

    def set_timerange(self, rg):
        """rg is a list [Timestamp, Timestamp]"""
        self.series = None

        if rg is None or rg == [None, None]:
            return

        # if a valid time range
        if (
            self.data is not None
            and self.data["time"].min() <= rg[0] < rg[1] <= self.data["time"].max()
        ):
            self.data["time"].values.min()
            self.timerange = rg
            self.__set_series()

    def __set_series(self, update_units=False):
        if not self.var:
            return

        if update_units:
            self.set_units(self.v2u.get(self.var, None))

        # no dimensions, probably csv
        if not self.v2d[self.var]:
            self.series = self.data[self.var]
        elif (
            self.dims
            and all(d in self.dims for d in self.v2d[self.var])
            and all(d in self.v2d[self.var] for d in self.dims)
        ):
            self.series = self.data[self.var].sel(self.dims).to_series()
        else:
            return

        # if there is a time range, select on that
        if self.timerange:
            start, end = self.timerange
            self.series = self.series.loc[start:end]

    def get_series(self):
        return self.series

    def set_units(self, u):
        self.units = u

    def get_units(self):
        return self.units

    def set_agg(self, a):
        if a in ["mean", "sum", "min", "max"]:
            self.agg = a

    def get_agg(self):
        return self.agg


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
            self.__set_var(v)

        # if agg set, inform sd
        a = self.parent.cp["DEFAULT"].get(f"{self.title}_agg")
        if a and a in ["mean", "sum", "max", "min"]:
            self.agg_cb.setCurrentText(a)
            self.__set_agg(a)

        # if dims set, inform sd
        d = self.parent.cp["DEFAULT"].get(f"{self.title}_dims")
        if d:
            # only set the dims if valid
            d2v = json.loads(d)
            if all([d in self.sd.d2vals and v in self.sd.d2vals[d] for d, v in d2v.items()]):
                self.sd.set_dims(d2v)

        # if timerange set, inform sd
        rg = self.parent.cp["DEFAULT"].get(f"{self.title}_timerange")
        if rg:
            start, end = [pd.Timestamp(s) for s in json.loads(rg)]
            # only set the range if valid, otherwise series is set to None
            if (
                self.sd.data is not None
                and self.sd.data["time"].min() <= start < end <= self.sd.data["time"].max()
            ):
                self.sd.set_timerange([start, end])

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
        cb.currentTextChanged.connect(self.__set_var)  # programmatically set, dont store in cp
        cb.activated.connect(self.__act_var)  # when user changes it we store in config
        hbox.addWidget(cb)

        # Aggregation label and dropdown
        hbox.addWidget(QLabel("Agg:"))
        self.agg_cb = cb = QComboBox()
        cb.addItems(["mean", "sum", "min", "max"])
        cb.setToolTip("How to aggregate this variable")
        cb.activated.connect(self.__act_agg)  # store in config
        hbox.addWidget(cb)

        # Dimensions button
        self.dims_btn = btn = QPushButton("Dims")
        self.dims_btn.clicked.connect(self.__act_dims)  # store in config
        hbox.addWidget(btn)

        # Datetime range button
        self.timerange_btn = btn = QPushButton("Time range")
        self.timerange_btn.clicked.connect(self.__act_timerange)  # user
        hbox.addWidget(btn)

        hbox.addStretch()

        # View button
        view_btn = QPushButton("View")
        view_btn.clicked.connect(self.view_data)
        hbox.addWidget(view_btn)

        # Plot button
        plot_btn = QPushButton("Plot")
        plot_btn.clicked.connect(self.plot_series)
        hbox.addWidget(plot_btn)

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

        # stored var, dims and time range don't make sense now
        self.parent.cp["DEFAULT"].pop(f"{self.title}_var", None)
        self.parent.cp["DEFAULT"].pop(f"{self.title}_dims", None)
        self.parent.cp["DEFAULT"].pop(f"{self.title}_timerange", None)
        self.parent.cp["DEFAULT"].pop(f"{self.title}_agg", None)

        self.parent.save_config()
        self.__set_sourcedata_file(fname)

    def __set_sourcedata_file(self, fname: pathlib.Path):
        self.fn_le.setText(fname.name)
        self.vars_cb.clear()
        self.dims_btn.setEnabled(fname.suffix.lower() == ".nc")

        # inform model/obs about new file
        try:
            guess = self.parent.cp["DEFAULT"].getboolean('guessnodata', False)
            if self.sd.read_fn(fname, guess):
                self.parent.cp["DEFAULT"]['guessnodata'] = "False"
                self.parent.save_config()
            self.vars_cb.addItems(self.sd.get_vars())
        except Exception as e:
            self.fn_le.setText("Click to select file")
            self.vars_cb.clear()
            self.dims_btn.setEnabled(False)
            QMessageBox.critical(self, "Error", f"Could not parse {fname}:\n{e}")

    def __set_var(self, v):
        self.sd.set_var(v)

    def __act_var(self, idx):
        """When user changes var we save it"""
        self.parent.cp["DEFAULT"][f"{self.title}_var"] = self.vars_cb.itemText(idx)
        # likely dims don't make any sense now, so remove
        self.parent.cp["DEFAULT"].pop(f"{self.title}_dims", None)
        self.parent.cp["DEFAULT"].pop(f"{self.title}_agg", None)
        self.parent.save_config()
        self.__set_var(self.vars_cb.itemText(idx))

    def __set_agg(self, a):
        self.sd.set_agg(a)

    def __act_agg(self, idx):
        """When user changes agg we save it"""
        self.parent.cp["DEFAULT"][f"{self.title}_agg"] = self.agg_cb.itemText(idx)
        self.parent.save_config()
        self.__set_agg(self.agg_cb.itemText(idx))

    def __set_dims(self, d2v):
        """dim_name to selected/entered value as strings"""
        self.sd.set_dims(d2v)

    def __act_dims(self):
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
            self.parent.save_config()
            self.__set_dims(selected_values)

    def __set_timerange(self, rg):
        """rg is [start Timestamp, end Timestamp]"""
        self.sd.set_timerange(rg)

    def __act_timerange(self):
        s = self.sd.get_series()
        if s is None:
            QMessageBox.warning(self, "No variable", "File/variable/dimension must be all set")
            return

        # see if there are defaults saved.  should get from self.sd
        rg = self.sd.get_timerange()

        # get the full time index from sd
        index = self.sd.data["time"]
        if hasattr(index, "values"):
            index = pd.to_datetime(index.values)

        dialog = TimeRangeSelectorDialog(index, start=rg[0], end=rg[1], parent=self.parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_values = dialog.get_values()
            self.parent.cp["DEFAULT"][f"{self.title}_timerange"] = json.dumps(
                [selected_values[0].isoformat(), selected_values[1].isoformat()]
            )
            self.parent.save_config()
            self.__set_timerange(selected_values)

    def view_data(self):
        d = self.sd.data
        if d is None:
            QMessageBox.warning(self, "No file", "Data file must be loaded")
            return

        class ViewDialog(QDialog):
            def __init__(self, parent, df):
                super().__init__(parent)
                self.setWindowTitle("Data summary")
                self.resize(700, 600)

                layout = QVBoxLayout(self)

                text = QPlainTextEdit()
                text.setReadOnly(True)
                text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

                if isinstance(df, (xr.DataArray, xr.Dataset)):
                    summary = repr(df)
                else:
                    summary = df.drop(columns=["time"]).to_string(max_rows=20, max_cols=10)
                text.setPlainText(summary)
                font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                text.setFont(font)

                layout.addWidget(text)
                b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
                b.accepted.connect(self.accept)
                layout.addWidget(b)

        dlg = ViewDialog(self, d)
        dlg.exec()

    def plot_series(self):
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



class GuessNoDataDialog(QDialog):
    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set NoData value")
        self.resize(500, 300)

        # maps var to my guess of nodata
        self.var2guess = var2guess = self._possible_nodatas(df)
        if not var2guess:
            return

        # we have some guesses.
        # we will present the dialog with all the variables and let user put values in

        # maps var to lineedit of nodata values
        self.var2le = {}
        # maps var to nodata values, populated after user hits OK
        self.var2nodata = {}

        layout = QVBoxLayout(self)

        top_label = QLabel(
            "<b>Warning:</b> You asked me to guess NoData values in .csv files.<br>"
            "This is not reliable, but I think the following might be "
            "NoData values. Update or leave blank if there is no NoData",
            wordWrap=True
        )
        top_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(top_label)

        flayout = QFormLayout()
        header_label_var = QLabel("Variable")
        header_label_var.setFont(QFont("", weight=QFont.Weight.Bold))
        header_label_nodata = QLabel("NoData")
        header_label_nodata.setFont(QFont("", weight=QFont.Weight.Bold))
        flayout.addRow(header_label_var, header_label_nodata)
        for var in df.columns:
            self.var2le[var] = le = QLineEdit()
            le.setValidator(QDoubleValidator())
            if var in var2guess:
                le.setText(str(var2guess[var]))
            le.setFixedWidth(70)
            flayout.addRow(var, le)

        layout.addLayout(flayout)

        bot_label = QLabel(
            "Automatically guessing NoData values is error prone. "
            "A better approach is to edit your .csv file yourself, "
            "replacing NoData values with blanks, which is the typical "
            "way of denoting missing values in a .csv file.",
            wordWrap=True
        )
        bot_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(bot_label)

        # Never show again checkbox
        self.never_show = QCheckBox("Never show this dialog again")
        layout.addWidget(self.never_show)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def ok(self):
        """Alter var2nodata to map var to the new nodata"""
        self.var2nodata = {}
        for var, le in self.var2le.items():
            try:
                val = float(le.text())
            except ValueError:
                continue
            self.var2nodata[var] = val
        self.accept()

    def _possible_nodatas(self, df):
        """Return dict of variable name to guessed NoData value"""
        candidates = {}

        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue

            series = df[col].dropna()
            if series.empty:
                continue

            q1 = series.quantile(0.1)
            q9 = series.quantile(0.9)
            iqr = q9 - q1
            if iqr == 0:
                continue
            lower = q1 - 5 * iqr
            upper = q9 + 5 * iqr

            # outside 5 IQRs
            outliers = series[(series < lower) | (series > upper)]
            if outliers.empty:
                continue

            # most frequent outlier is first
            candidates[col] = outliers.value_counts().index[0]

        return candidates




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


class TimeRangeSelectorDialog(QDialog):
    def __init__(self, index, start=None, end=None, parent=None):
        """
        Parameters
        ----------
        index: Datetime index
            Restrict selectable range

        start: pd.Timestamp (optional)
            Initial from value

        end: pd.Timestamp (optional)
            Initial to value

        """
        super().__init__(parent)
        self.setWindowTitle("Select time range")

        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.addWidget(QLabel("From"), 0, 0)
        grid.addWidget(QLabel("To"), 1, 0)

        self.from_edit = QDateTimeEdit()
        self.to_edit = QDateTimeEdit()
        for w in (self.from_edit, self.to_edit):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        # index is garanteed to have at least two items
        idx_min = index.min()
        idx_max = index.max()
        qmin = QDateTime(idx_min)
        qmax = QDateTime(idx_max)
        self.from_edit.setMinimumDateTime(qmin)
        self.from_edit.setMaximumDateTime(qmax)
        self.to_edit.setMinimumDateTime(qmin)
        self.to_edit.setMaximumDateTime(qmax)
        if start is None:
            start = idx_min
        if end is None:
            end = idx_max

        self.from_edit.setDateTime(QDateTime(start))
        self.to_edit.setDateTime(QDateTime(end))
        grid.addWidget(self.from_edit, 0, 1)
        grid.addWidget(self.to_edit, 1, 1)

        # need to set up buttons now because if line_edit is used then disable Ok button until input
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(True)

        layout.addLayout(grid)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

        # validate range
        self.from_edit.dateTimeChanged.connect(self._validate)
        self.to_edit.dateTimeChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        """Disable OK if from > to."""
        start = self.from_edit.dateTime()
        end = self.to_edit.dateTime()
        self.ok_button.setEnabled(start <= end)

    def get_values(self):
        """
        Return a tuple (start datetime, end datetime)
        """
        start = pd.Timestamp(self.from_edit.dateTime().toPyDateTime())
        end = pd.Timestamp(self.to_edit.dateTime().toPyDateTime())
        return (start, end)
