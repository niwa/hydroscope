#!/usr/bin/env python

import os
import sys
import pathlib
import configparser
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDialog,
    QDialogButtonBox,
    QMenu,
    QWidget,
    QVBoxLayout, QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
    QGroupBox,
    QMessageBox
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
from PyQt6.QtCore import QTimer
import platformdirs
import utils
import updates
import sourcedata
import purpose
import results

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

        # config file
        dirs = platformdirs.PlatformDirs('Hydroscope', 'NIWA')
        self.cdir = cdir = pathlib.Path(dirs.user_data_dir)
        os.makedirs(cdir, mode=0o755, exist_ok=True)
        self.cfile = cdir / 'config.ini'
        self.load_config()

        # the model
        self.model = sourcedata.SourceData()

        # the obs
        self.obs = sourcedata.SourceData()

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

        md = sourcedata.SourceDataWidget(self.model, title='Model', parent=self)
        vbox.addWidget(md)

        od = sourcedata.SourceDataWidget(self.obs, title='Observations', parent=self)
        vbox.addWidget(od)

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
                    QMessageBox.critical(self, "Error", "Peak number and width and BFI passes must be integers")
                    return False
             
                try:
                    ba = float(self.bfi_alpha.text())
                except Exception as exp:
                    QMessageBox.critical(self, "Error", "BFI alpha must be a float")
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
                self.parent.save_config()

                return super().accept()

        dl = SettingsDialog(self)
        dl.exec()

    def calculate(self, purp: str):
        """Calculate the given metric if possible"""
        m = self.model.get_series()
        o = self.obs.get_series()
        if m is None or o is None:
            QMessageBox.warning(self, "No data", "Need model and obs data defined first")
            return
        self.rd.calculate(purp, m, o)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    win.raise_()
    sys.exit(app.exec())
