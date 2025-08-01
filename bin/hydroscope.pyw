#!/usr/bin/env python

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
import pandas as pd
import xarray as xr
import model

class Window(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HydroScope")

        # icon
        if getattr(sys, "frozen", False):
            fname = pathlib.Path(sys._MEIPASS) / "hydroscope.ico"
        else:
            me = pathlib.Path(sys.argv[0]).resolve()
            fname = me.parent.parent / "etc" / "hydroscope.ico"
        # on linux we need a ppm/pgm file, not a windows ico, just ignore
        try:
            self.setWindowIcon(QIcon(str(fname)))
        except Exception:
            pass

        # we need proper project stuff, but in the meantime hack this in
        self.lastdir = pathlib.Path(platformdirs.user_downloads_dir())

        # the model
        self.model = model.Model()

        self.setCentralWidget(self.__create_main())
        self.__create_menus()

        updates.possibly_update(self)

    def set_lastdir(self, p):
        self.lastdir = p

    def get_lastdir(self):
        return self.lastdir

    def __create_menus(self):
        bar = self.menuBar()

        menu = QMenu("&File", self)
        bar.addMenu(menu)
        action = QAction("&Quit", self)
        action.triggered.connect(self.close)
        menu.addAction(action)

        menu = QMenu("&Help", self)
        bar.addMenu(menu)
        action = QAction("&About", self)
        action.triggered.connect(lambda: utils.msg(self, "About", "version.txt"))
        menu.addAction(action)
        action = QAction("&Update", self)
        action.triggered.connect(lambda: updates.check_for_updates(self))
        menu.addAction(action)
        action = QAction("&Help", self)
        action.triggered.connect(lambda: utils.msg(self, "Help", "help.html"))
        menu.addAction(action)

    def __create_main(self) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)

        # Model
        """
        title = QLabel(f"Model output")
        vbox.addWidget(title)

        hbox = QHBoxLayout()

        # Model output file
        hbox.addWidget(QLabel("File:"))
        self.model_label = lab = utils.ClickableLineEdit("Click to select file", char_width=15)
        self.model_fn = None
        lab.clicked.connect(self.select_model_file)
        self.model_changed.connect(self.set_model_variables)
        self.model_changed.connect(self.toggle_model_dims)
        hbox.addWidget(lab)

        # Variable label and dropdown
        hbox.addWidget(QLabel("Variable:"))
        self.model_variables_cb = cb = QComboBox()
        hbox.addWidget(cb)

        # Dimensions button
        self.model_dims_btn = btn = QPushButton("Dimensions")
        self.model_dims_btn.clicked.connect(self.set_model_dims)
        hbox.addWidget(btn)

        # Optional: Add stretch at the end to push widgets left
        hbox.addStretch()

        # View button
        view_button = QPushButton("View")
        hbox.addWidget(view_button)

        """
        md = model.ModelWidget(self.model, self)
        vbox.addWidget(md)

        # Obs
        title = QLabel(f"Observations")
        hbox = QHBoxLayout()
        vbox.addWidget(title)
        vbox.addLayout(hbox)

        # Metrics
        title = QLabel(f"Purpose and metrics")
        hbox = QHBoxLayout()
        vbox.addWidget(title)
        vbox.addLayout(hbox)

        # Results
        title = QLabel(f"Results")
        hbox = QHBoxLayout()
        vbox.addWidget(title)
        vbox.addLayout(hbox)


        return widget
    
    """
    def select_model_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select a file", str(self.opendir), "NetCDF or CSV Files (*.nc *.csv)")
        if fname:
            fname = pathlib.Path(fname)
            self.opendir = fname.parent
            self.model_label.setText(fname.name)
            self.model_fn = fname
            self.model_changed.emit(fname)

    
    def set_model_variables(self, path: pathlib.Path):
        try:
            if path.suffix.lower() == ".csv":
                self.model_data = df = pd.read_csv(path, index_col=0, parse_dates=True)
                variables = df.columns.tolist()
            elif path.suffix.lower() == ".nc":
                self.model_data = ds = xr.open_dataset(path)
                variables = list(ds.data_vars.keys())
            else:
                raise ValueError("Unsupported file format")

            # Example of a format check
            if not variables:
                raise ValueError("No variables found in file")

            self.model_variables_cb.clear()
            self.model_variables_cb.addItems(variables)

        except Exception as e:
            self.model_data = None
            self.model_fn = None
            self.model_label.setText("Click to select model")


    def toggle_model_dims(self, path: pathlib.Path):
        if path.suffix.lower() == ".nc":
            self.model_dims_btn.setEnabled(True)
        else:
            self.model_dims_btn.setEnabled(False)

    """
    """
    def set_model_dims(self, path: pathlib.Path):
        vname = self.model_variables_cb.currentText()
        if not vname:
            QMessageBox.warning(self, "No Variable", "Please select a variable.")
            return

        try:
            if self.model_data is not None:
                if vname not in self.model_data:
                    raise KeyError(f"Variable '{vname}' not found in {self.model_fn}")
                dims = self.model_data[vname].dims
                shape = self.model_data[vname].shape
                dim_info = f"NetCDF variable '{vname}': dims = {dims}, shape = {shape}"
            else:
                raise RuntimeError("No data loaded.")

            QMessageBox.information(self, "Variable Dimensions", dim_info)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get dimensions:\n{str(e)}")

    """

    """
    def set_model_dims(self, path: pathlib.Path):
        vname = self.model_variables_cb.currentText()
        if not vname:
            QMessageBox.warning(self, "No Variable", "Please select a variable.")
            return

        try:
            if self.model_data is not None:
                if vname not in self.model_data:
                    raise KeyError(f"Variable '{vname}' not found in {self.model_fn}")
                dims = [d for d in self.model_data[vname].dims if not re.search('time|date', d, re.IGNORECASE)]
                dim2vals = {}
                for dim in dims:
                    vals = self.model_data.coords.get(dim, None)
                    if vals is not None:
                        dim2vals[dim] = vals.values.tolist()
                    else:
                        # no coordinate values, use just range indices
                        dim2vals[dim] = list(range(self.model_data.dims[dim]))
            else:
                raise RuntimeError("No data loaded.")

            dialog = dimensions.DimensionSelectorDialog(dim2vals, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_values = dialog.get_values()
                # You can do something with selected_values here
                # For example, print or store them:
                print("Selected dimension values:", selected_values)
                # Maybe store in self or use to subset dataset etc.

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get dimensions:\n{str(e)}")

    """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
