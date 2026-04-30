#!/usr/bin/env python

import os
import sys
import pathlib
import configparser
import platformdirs
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QApplication,
    QMainWindow,
    QDialog,
    QDialogButtonBox,
    QMenu,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QCheckBox,
    QComboBox,
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
from PyQt6.QtCore import QTimer, pyqtSignal
import utils
import updates
import sourcedata
import purpose
import results
import datasets_panel
import dataset_editor
import dataset

class Window(QMainWindow):
    datasetUpdated = pyqtSignal(object)

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

        # config file
        dirs = platformdirs.PlatformDirs('Hydroscope', 'NIWA')
        self.cdir = cdir = pathlib.Path(dirs.user_data_dir)
        os.makedirs(cdir, mode=0o755, exist_ok=True)
        self.cfile = cdir / 'config.ini'
        self.load_config()

        # list of datasets
        guess = self.cp["DEFAULT"].getboolean("guessnodata", fallback=False)                       
        self.datasets = []
        badsecs = []
        for section in self.cp.sections():
            if section.startswith("dataset_"):
                try:
                    d = dataset.Dataset.from_config_dict(self.cp[section], guessnodata=guess)
                except Exception:
                    badsecs.append(section)
                else:
                    self.datasets.append(d)
                 
        self.dstm = datasets_panel.DataSetsTableModel(self.datasets)
        for s in badsecs:
            self.cp.remove_section(s)
        self.save_config()

        # so when Adding or Removing we update config
        self.dstm.datasetsChanged.connect(self.update_config_from_model)
        self.dstm.dataChanged.connect(self.update_config_from_model)

        # the results logic
        if getattr(sys, "frozen", False):
            fname = pathlib.Path(sys._MEIPASS) / "metrics.json"
        else:
            me = pathlib.Path(sys.argv[0]).resolve()
            fname = me.parent.parent / "etc" / "metrics.json"
        self.results = results.Results(self.cp["DEFAULT"], fname)

        self.setCentralWidget(self.__create_main())
        self.__create_menus()

        # I think this ensures that the main window is displayed before doing update dialog, which helps visibility
        QTimer.singleShot(0, lambda : updates.possibly_update(self))

    def load_config(self):
        # put in default config file if necessary
        if not self.cfile.exists():
            cp = configparser.ConfigParser()
            cp['DEFAULT'] = {
                'lastdir': platformdirs.user_downloads_dir()
            }
            with open(self.cfile, 'w') as cfh:
                cp.write(cfh)

        self.cp = configparser.ConfigParser()
        self.cp.read(self.cfile)

    def update_config_from_model(self):
        for section in self.cp.sections():
            if section.startswith("dataset_"):
                self.cp.remove_section(section)

        for i, cfg in enumerate(self.dstm.to_config_dicts()):
            section = f"dataset_{i}"
            self.cp[section] = cfg

        self.save_config()

    def save_config(self):
        with open(self.cfile, 'w') as cfh:
            self.cp.write(cfh)

    def __create_menus(self):
        bar = self.menuBar()

        menu = QMenu("&File", self)
        bar.addMenu(menu)
        action = QAction("&Save", self)
        action.triggered.connect(self.save_config)
        menu.addAction(action)
        action = QAction("&Settings", self)
        action.triggered.connect(self.__settings)
        menu.addAction(action)
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

        # dataset table and editor layout
        ds_layout = QHBoxLayout()
        self.dataset_panel = datasets_panel.DatasetsPanel(self.dstm, parent=self)
        self.dataset_editor = dataset_editor.DatasetEditor(parent=self)
        ds_layout.addWidget(self.dataset_panel)
        ds_layout.addWidget(self.dataset_editor)
        self.dataset_panel.datasetSelected.connect(self._dataset_selected)
        self.dataset_editor.datasetFieldChanged.connect(self._dataset_field_changed)

        vbox.addLayout(ds_layout)

        if getattr(sys, "frozen", False):
            fname = pathlib.Path(sys._MEIPASS) / "metrics.json"
        else:
            me = pathlib.Path(sys.argv[0]).resolve()
            fname = me.parent.parent / "etc" / "metrics.json"
        metbox = purpose.PurposeWidget('Purpose and metrics', fname, self)
        vbox.addWidget(metbox)

        # Results
        self.rd = rd = results.ResultsWidget(self.results, title='Results', parent=self)
        vbox.addWidget(rd)

        return widget
 
    def _dataset_selected(self, ds):
        self.current_dataset = ds
        self.dataset_editor.load_dataset(ds)

    def _dataset_field_changed(self, field, value):
        ds = self.current_dataset
        if ds is None:
            return

        if field == "name":
            ds.name = value
            # this ensures the series has the correct name
            ds.set_series(ds.get_var(), ds.get_dims(), ds.get_timerange())
        elif field == "var":
            ds.set_series(value, ds.get_dims(), ds.get_timerange())
        elif field == "dims":
            ds.set_series(ds.get_var(), value, ds.get_timerange())
        elif field == "agg":
            ds.set_agg(value)
        elif field == "timerange":
            ds.set_series(ds.get_var(), ds.get_dims(), value)

        self.dstm.dataset_changed(ds)
        self.datasetUpdated.emit(ds)

    def __settings(self):
        class SettingsDialog(QDialog):
            def __init__(self, parent):
                super().__init__(parent)
                self.parent = parent
                self.setWindowTitle("Settings")
                btns = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                btns.accepted.connect(self.accept)
                btns.rejected.connect(self.reject)
                layout = QFormLayout()

                cp = parent.cp["DEFAULT"]

                self.peak_num = num = QLineEdit()
                if val := cp.get("peak_num", "10"):
                    num.setText(val)
                num.setToolTip("Number of high flow peaks to analyse")

                self.peak_gap = pg = QLineEdit()
                if val := cp.get("peak_gap", "7"):
                    pg.setText(val)
                pg.setToolTip("Minimum number of days between high flow peaks")

                layout.addRow("Peaks:", num)
                layout.addRow("Peak gap (days):", pg)

                self.bfi_alpha = bfi = QLineEdit()
                if val := cp.get("bfi_alpha", "0.925"):
                    bfi.setText(val)
                bfi.setToolTip("Alpha filter parameter for BFI Lyne and Hollick filter")

                self.bfi_np = np = QLineEdit()
                if val := cp.get("bfi_np", "3"):
                    np.setText(val)
                np.setToolTip("Number of filter passes for BFI Lyne and Hollick filter")

                layout.addRow("BFI alpha:", bfi)
                layout.addRow("BFI passes:", np)

                self.ye = ye = QComboBox()
                ye.addItems(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
                ye.setToolTip("Last month of the year for defining seasonal and annual aggregation")
                if val := cp.get("lastmonthofyear", "Dec"):
                    ye.setCurrentText(val)
                layout.addRow("Last month of year:", ye)

                self.aggregation = ag = QCheckBox()
                val = cp.getboolean("aggregation", fallback=False)
                ag.setChecked(val)
                ag.setToolTip("Allow time aggregation for model or obs data")
                layout.addRow("Aggregation:", ag)

                self.guessnodata = gn = QCheckBox()
                val = cp.getboolean("guessnodata", fallback=False)
                gn.setChecked(val)
                gn.setToolTip("Attempt to guess nodata value in .csv")
                layout.addRow("Guess NoData:", gn)

                layout.addWidget(btns)
                self.setLayout(layout)

            def accept(self):
                """Test and possibly save."""
                if not (self.peak_num.text() and self.peak_gap.text()):
                    QMessageBox.critical(self, "Error", "Specify number and width of peaks")
                    return False
              
                if not (self.bfi_alpha.text() and self.bfi_np.text()):
                    QMessageBox.critical(self, "Error", "Specify BFI alpha and number of passes")
                    return False
              
                try:
                    n = int(self.peak_num.text())
                    p = int(self.peak_gap.text())
                    bn = int(self.bfi_np.text())
                except Exception as exp:
                    QMessageBox.critical(self, "Error", f"Peak number and width and BFI passes must be integers: {exp}")
                    return False
             
                try:
                    ba = float(self.bfi_alpha.text())
                except Exception as exp:
                    QMessageBox.critical(self, "Error", f"BFI alpha must be a float {exp}")
                    return False
             
                if n < 1 or p < 1:
                    QMessageBox.critical(self, "Error", "Peak number and width must be positive")
                    return False

                if bn < 1:
                    QMessageBox.critical(self, "Error", "BFI passes must be positive")
                    return False

                if ba <= 0 or ba >= 1:
                    QMessageBox.critical(self, "Error", "BFI alpha must be in (0, 1)")
                    return False

                self.parent.cp["DEFAULT"]["peak_num"] = str(n)
                self.parent.cp["DEFAULT"]["peak_gap"] = str(p)
                self.parent.cp["DEFAULT"]["bfi_alpha"] = str(ba)
                self.parent.cp["DEFAULT"]["bfi_np"] = str(bn)
                self.parent.cp["DEFAULT"]["lastmonthofyear"] = self.ye.currentText()
                self.parent.cp["DEFAULT"]["aggregation"] = str(self.aggregation.isChecked())
                self.parent.cp["DEFAULT"]["guessnodata"] = str(self.guessnodata.isChecked())
                self.parent.save_config()

                return super().accept()

        dl = SettingsDialog(self)
        dl.exec()

    def calculate(self, purp: str):
        """Calculate the given metric if possible"""
        r = [d for d in self.datasets if d.include and d.ref]
        nr = [d for d in self.datasets if d.include and not d.ref]
        if len(r) != 1 or len(nr) < 1:
            QMessageBox.warning(self, "No data", "Need exactly one reference dataset, and at least one more")
            return

        r = r[0]
        return self.rd.calculate(
            purp,
            [d.get_series() for d in nr], r.get_series(),
            [d.get_units() for d in nr], r.get_units(),
            [d.get_agg() for d in nr], r.get_agg(),
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    win.raise_()
    sys.exit(app.exec())
