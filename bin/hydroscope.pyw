#!/usr/bin/env python

import sys
import pathlib
import requests
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QTextEdit,
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)


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

        self.__create_menus()

        # get the latest version, and store my version in self.version
        self.version = "unknown"
        self.possibly_update()

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
        action.triggered.connect(lambda: self.msg("About", "version.txt"))
        menu.addAction(action)
        action = QAction("&Check for updates", self)
        action.triggered.connect(self.check_for_updates);
        menu.addAction(action)
        action = QAction("&Help", self)
        action.triggered.connect(lambda: self.msg("Help", "help.html"))
        menu.addAction(action)

    def check_for_updates(self):

        class VersionDialog(QDialog):
            def __init__(self, parent, pver: str, ghver: str):
                super().__init__(parent)
                self.setWindowTitle("Versions")

                layout = QVBoxLayout(self)
                grid = QGridLayout()
                layout.addLayout(grid)


                grid.addWidget(QLabel("This version:"), 0, 0)
                grid.addWidget(QLabel(pver), 0, 1)

                grid.addWidget(QLabel("Github code version:"), 1, 0)
                grid.addWidget(QLabel(ghver), 1, 1)


                btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
                btns.accepted.connect(self.accept)
                layout.addWidget(btns)


        cver = self.get_prog_version() or 'unknown'
        ghver = self.get_github_version() or 'unknown'
        dia = VersionDialog(self,cver, ghver)
        dia.exec()

    def __parse_version_txt(self, contents):
        """Return None or version string

        Parameters
        ----------
        contents: str
            The contents of version.txt file

        Returns
        -------
        None or str
            On any error return None, else return a string version like 1.2.3
        """
        try:
            return [ln.split("Version: ", 1)[1].strip() for ln in contents.splitlines() if ln.startswith("Version: ")][0]
        except:
            return None

    def get_prog_version(self):
        """Return version of this running program or None"""

        fname = 'version.txt'
        if getattr(sys, "frozen", False):
            fname = pathlib.Path(sys._MEIPASS) / fname
        else:
            me = pathlib.Path(sys.argv[0]).resolve()
            fname = me.parent / fname

        try:
            with open(fname) as fh:
                return(self.__parse_version_txt(fh.read()))
        except:
            return None
        
    def get_github_version(self):
        url = "https://raw.githubusercontent.com/niwa/hydroscope/main/bin/version.txt"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return self.__parse_version_txt(r.text)
        except:
            return None
    

    def get_installable_versions(self):
        pass

    def possibly_update(self):
        return

    def msg(self, title, fname):
        class ScrollableDialog(QDialog):
            def __init__(self, title, txt, parent=None, html=False):
                super().__init__(parent)
                self.setWindowTitle(title)
                btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
                btns.accepted.connect(self.accept)
                layout = QVBoxLayout()
                te = QTextEdit()
                if html:
                    te.setHtml(txt)
                else:
                    te.setText(txt)
                te.setMinimumWidth(600)
                te.setMinimumHeight(400)
                te.setReadOnly(True)
                layout.addWidget(te)
                layout.addWidget(btns)
                self.setLayout(layout)

        if getattr(sys, "frozen", False):
            fname = pathlib.Path(sys._MEIPASS) / fname
        else:
            me = pathlib.Path(sys.argv[0]).resolve()
            fname = me.parent / fname

        with open(fname) as fh:
            txt = fh.read()
            # if txt is short a messagebox will do
            if txt.count("\n") < 5:
                QMessageBox.information(self, "About", txt)
            else:
                dl = ScrollableDialog(
                    title, txt, parent=self, html=pathlib.Path(fname).suffix == ".html"
                )
                dl.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
