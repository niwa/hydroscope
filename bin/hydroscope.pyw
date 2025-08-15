#!/usr/bin/env python

import os
import sys
import pathlib
import configparser
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel,
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
import platformdirs
import utils
import updates
import sourcedata

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

        self.setCentralWidget(self.__create_main())
        self.__create_menus()

        updates.possibly_update(self)

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

        od = sourcedata.SourceDataWidget(self.obs, title='Obs', parent=self)
        vbox.addWidget(od)


        # Metrics
        title = QLabel("Purpose and metrics")
        hbox = QHBoxLayout()
        vbox.addWidget(title)
        vbox.addLayout(hbox)

        # Results
        title = QLabel("Results")
        hbox = QHBoxLayout()
        vbox.addWidget(title)
        vbox.addLayout(hbox)

        return widget
    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
