import re
import json
import numpy as np
import pandas as pd
import xarray as xr
import pathlib

from PyQt6.QtGui import QDoubleValidator, QFont
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QFormLayout,
)


class Dataset:
    def __init__(self, fn, guessnodata: bool):

        # supposed to be included in analysis
        self.include = True
        # the reference or obs dataset
        self.ref = False
        # the name (this is just for the user)
        self.name = fn.stem

        self.fn = fn
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
            df.index.name = "time"
            if guessnodata:
                dlg = GuessNoDataDialog(df)
                if dlg.var2guess and dlg.exec():
                    for var, val in dlg.var2nodata.items():
                        df.loc[df[var] == val, var] = np.nan
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

        # first variable and first lot of dims
        self.set_series("", {}, [None, None])

    def to_config_dict(self):
        def encode_ts(ts):
            return None if ts is None else ts.isoformat()

        return {
            "name": self.name or "",
            "var": self.var or "",
            "agg": self.agg or "mean",
            "dims": json.dumps(self.dims),
            "filename": str(self.fn),
            "include": str(int(self.include)),
            "ref": str(int(self.ref)),
            "timerange": json.dumps([encode_ts(self.timerange[0]), encode_ts(self.timerange[1])]),
        }

    @classmethod
    def from_config_dict(cls, cfg: dict, guessnodata: bool):
        def decode_ts(ts):
            return None if ts is None else pd.Timestamp(ts)

        filename = pathlib.Path(cfg["filename"])
        tr = json.loads(cfg["timerange"])
        d = Dataset(filename, guessnodata)

        d.name = cfg["name"]
        d.include = bool(int(cfg["include"]))
        d.ref = bool(int(cfg["ref"]))
        d.set_agg(cfg["agg"])
        d.set_series(cfg["var"], json.loads(cfg["dims"]), [decode_ts(tr[0]), decode_ts(tr[1])])

        return d

    def get_var(self):
        return self.var

    def get_vars(self):
        return self.vars

    def get_d2type(self):
        return self.d2type

    def get_d2vals(self, v):
        """Return a dict from dim to possible values for given variable"""
        if v not in self.v2d:
            return {}
        return {d: self.d2vals[d] for d in sorted(self.v2d[v])}

    def get_dims(self):
        return self.dims

    def get_timerange(self):
        return self.timerange

    def get_series(self):
        return self.series

    def get_units(self):
        return self.units

    def set_agg(self, a):
        if a in ["mean", "sum", "min", "max"]:
            self.agg = a

    def get_agg(self):
        return self.agg

    def set_series(self, v, dims, tr):
        """Set the series using var, dims and tr

        This ensures the series will be set.  Possibly v, dims, and tr will be all
        changed to accomplish this.  In the normal course of events v, dims, and tr
        will make sense for this dataset, however if the user changes the
        contents of self.fn outside this program, then the saved dataset info
        will not make sense.

        Parameters
        ----------
        v: str
            The variable, if it doesn't exist in this dataset, self.vars[0]
            will be used

        dims: dict
            The dimensions.  If these don't make sense for v, the first set of
            dimensions that work for v will be used

        tr: list
            [pd.Timestamp or None, pd.Timestamp or None]

        """

        self.var = self.vars[0] if v not in self.vars else v

        # possibly alter the dims
        if not (
            sorted(dims.keys()) == sorted(self.v2d[self.var])
            and all([d in self.d2vals and v in self.d2vals[d] for d, v in dims.items()])
        ):
            dims = {d: v[0] for d, v in self.get_d2vals(self.var).items()}
        self.dims = dims

        self.units = self.v2u.get(self.var, None)

        # no dimensions, probably csv
        if not self.dims:
            self.series = self.data[self.var]
        else:
            self.series = self.data[self.var].sel(self.dims).to_series()

        # time range
        def _clamp_ts(ts, lo, hi):
            if ts is None:
                return None
            return min(max(ts, lo), hi)

        tr[0] = _clamp_ts(tr[0], self.series.index.min(), self.series.index.max())
        tr[1] = _clamp_ts(tr[1], self.series.index.min(), self.series.index.max())
        if None not in tr and tr[0] > tr[1]:
            tr[0], tr[1] = tr[1], tr[0]

        self.timerange = tr
        self.series = self.series.loc[tr[0] : tr[1]]

        self.series.name = f"{self.name}_{self.series.name}"


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
            wordWrap=True,
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
            wordWrap=True,
        )
        bot_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(bot_label)

        # Never show again checkbox
        # self.never_show = QCheckBox("Never show this dialog again")
        # layout.addWidget(self.never_show)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
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
