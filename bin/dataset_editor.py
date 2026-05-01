import numpy as np
import pandas as pd
import utils
import xarray as xr
import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtGui import QRegularExpressionValidator, QFontDatabase
from PyQt6.QtCore import pyqtSignal, QRegularExpression, QDateTime
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QLineEdit,
    QComboBox,
    QFormLayout,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QDateTimeEdit,
    QPlainTextEdit,
)


class DatasetEditor(QWidget):
    datasetFieldChanged = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.ds = None
        parent.datasetUpdated.connect(self.load_dataset)

        vbox = QVBoxLayout(self)

        form = QFormLayout()

        self.name = n = QLineEdit()
        self.name.editingFinished.connect(
            lambda: self.datasetFieldChanged.emit(
                "name",
                self.name.text(),
            )
        )
        n.setToolTip("Name this dataset")
        form.addRow("Name:", n)

        self.fn_le = n = QLineEdit()
        n.setReadOnly(True)
        form.addRow("File:", n)

        self.vars_cb = cb = QComboBox()
        self.vars_cb.currentTextChanged.connect(
            lambda txt: self.datasetFieldChanged.emit(
                "var",
                txt,
            )
        )
        cb.setToolTip("Variable to use")
        cb.setMinimumWidth(100)
        form.addRow("Variable:", cb)

        self.agg_cb = cb = QComboBox()
        self.agg_cb.currentTextChanged.connect(
            lambda txt: self.datasetFieldChanged.emit(
                "agg",
                txt,
            )
        )
        cb.setToolTip("How to aggregate this variable")
        cb.addItems(["mean", "sum", "min", "max"])
        form.addRow("Agg:", cb)

        self.dims = n = utils.ClickableLineEdit("", char_width=100)
        n.setMinimumWidth(100)
        n.clicked.connect(self.__edit_dims)
        n.setToolTip("Set the dims")
        form.addRow("Dims:", n)

        range_layout = QHBoxLayout()
        self.start_edit = se = utils.ClickableLineEdit("")
        self.end_edit = ee = utils.ClickableLineEdit("")
        range_layout.addWidget(se)
        range_layout.addWidget(QLabel("-"))
        range_layout.addWidget(ee)
        se.clicked.connect(self.__edit_timerange)
        ee.clicked.connect(self.__edit_timerange)
        form.addRow("Time range:", range_layout)

        title = QLabel("Dataset")
        title.setStyleSheet("""font-size: 14px; font-weight: bold; padding: 0px;""")
        vbox.addWidget(title)
        vbox.addLayout(form)
        vbox.addStretch()

        hbox = QHBoxLayout()
        hbox.addStretch()

        # View button
        view_btn = QPushButton("View")
        view_btn.clicked.connect(self.view_data)
        hbox.addWidget(view_btn)

        # Plot button
        plot_btn = QPushButton("Plot")
        plot_btn.clicked.connect(self.plot_series)
        hbox.addWidget(plot_btn)

        vbox.addLayout(hbox)

        self.setEnabled(False)

    def load_dataset(self, ds):
        if ds is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self.ds = ds

        # name
        self.name.setText(ds.name)
        self.name.setCursorPosition(0)

        # fn
        self.fn_le.setText(str(ds.fn))
        self.fn_le.setCursorPosition(0)

        # var
        self.vars_cb.blockSignals(True)
        self.vars_cb.clear()
        self.vars_cb.addItems(ds.get_vars())
        idx = self.vars_cb.findText(ds.get_var())
        self.vars_cb.setCurrentIndex(np.clip(idx, 0, len(ds.get_vars()) - 1))
        self.vars_cb.blockSignals(False)

        # agg
        self.agg_cb.setCurrentText(ds.get_agg())

        # dims
        dims = ds.get_dims()
        self.dims.clear()
        self.dims.setEnabled(dims != {})
        if dims:
            self.dims.setText(str(dims))
            self.dims.setCursorPosition(0)

        # timerange
        tr = ds.get_timerange()

        def _fmt_ts(ts):
            if ts is None:
                return ""
            return str(ts)

        self.start_edit.setText(_fmt_ts(tr[0]))
        self.end_edit.setText(_fmt_ts(tr[1]))
        self.start_edit.setCursorPosition(0)
        self.end_edit.setCursorPosition(0)

    def __edit_dims(self):
        if not (
            self.ds and (v := self.vars_cb.currentText()) and (d2vals := self.ds.get_d2vals(v))
        ):
            return

        d = DimensionSelectorDialog(
            d2vals, self.ds.get_d2type(), self.ds.get_dims(), parent=self.parent
        )
        if d.exec() == QDialog.DialogCode.Accepted:
            self.datasetFieldChanged.emit("dims", d.get_values())

    def __edit_timerange(self):
        if not self.ds or self.ds.get_series() is None:
            return

        rg = self.ds.get_timerange()
        index = self.ds.get_series().index
        d = TimeRangeSelectorDialog(index, start=rg[0], end=rg[1], parent=self.parent)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.datasetFieldChanged.emit("timerange", d.get_values())

    def view_data(self):
        if not self.ds or (d := self.ds.data) is None:
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
        if not self.ds or (s := self.ds.get_series()) is None:
            return

        class PlotDialog(QDialog):
            def __init__(self, parent, series):
                super().__init__(parent)
                self.setWindowTitle("Series Plot")

                layout = QVBoxLayout(self)

                # dim string
                dims = parent.ds.get_dims()
                if dims:
                    dstr = [f"{dim}={val}" for dim, val in dims.items()]
                    dstr = f" ({','.join(dstr)})"
                else:
                    dstr = ""

                # Create Matplotlib Figure
                fig, ax = plt.subplots()
                series.plot(ax=ax)
                ax.set_title(f"{parent.ds.get_var()}{dstr}")
                ax.set_xlabel("Time")

                # if there is a name, use it
                lab = series.name if series.name else "Value"
                if u := parent.ds.get_units():
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
        return [start, end]
