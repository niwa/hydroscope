#!/usr/bin/env python

import sys
import pathlib
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel,
    QPushButton
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
import utils
import updates

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

        self.setCentralWidget(self.__create_main())
        self.__create_menus()

        updates.possibly_update(self)

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

        for i in range(4):
            title = QLabel(f"Section {i+1}")
            hbox = QHBoxLayout()

            # Just add sample content to each HBox for demo
            hbox.addWidget(QPushButton(f"Button A{i+1}"))
            hbox.addWidget(QPushButton(f"Button B{i+1}"))

            vbox.addWidget(title)
            vbox.addLayout(hbox)

        return widget

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
