import sys
import pathlib
from PyQt6.QtWidgets import (
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QTextEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QFileDialog, QVBoxLayout
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QCursor
import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QFileDialog, QVBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QMouseEvent, QFontMetrics


def msg(parent, title, fname):
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
            QMessageBox.information(parent, "About", txt)
        else:
            dl = ScrollableDialog(
                title, txt, parent=parent, html=pathlib.Path(fname).suffix == ".html"
            )
            dl.exec()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))  # make it look clickable

    def mousePressEvent(self, event):
        self.clicked.emit()


class ClickableLineEdit(QLineEdit):
    def __init__(self, text='', char_width=15, parent=None):
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Set fixed width based on character count
        font_metrics = QFontMetrics(self.font())
        width = font_metrics.horizontalAdvance('X' * char_width) + 10
        self.setFixedWidth(width)

    def mousePressEvent(self, event):
        self.clicked.emit()

