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
    QPushButton,
    QComboBox,
    QFileDialog
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

        # Model
        title = QLabel(f"Model output")
        vbox.addWidget(title)

        hbox = QHBoxLayout()

        # Model output file
        hbox.addWidget(QLabel("File:"))
        self.model_label = lab = utils.ClickableLineEdit("Click to select file", char_width=15)
        #= utils.ClickableLabel("Click to select file")
        self.model_fn = None
        lab.clicked.connect(self.select_file)
        hbox.addWidget(lab)


        # Variable label and dropdown
        hbox.addWidget(QLabel("Variable:"))
        variable_dropdown = QComboBox()
        variable_dropdown.addItems(["Option 1", "Option 2", "Option 3"])  # Example items
        hbox.addWidget(variable_dropdown)

        # Dimensions button
        dimensions_button = QPushButton("Dimensions")
        hbox.addWidget(dimensions_button)

        # Optional: Add stretch at the end to push widgets left
        hbox.addStretch()

        # View button
        view_button = QPushButton("View")
        hbox.addWidget(view_button)


        vbox.addLayout(hbox)

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

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select a file")
        if fname:
            self.model_label.setText(fname)
            self.model_fn = fname

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
