import sys
import pathlib
from PyQt6.QtWidgets import (
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QTextEdit,
)


def confirm_and_run(parent, msg, fun):
    """Display confirmation message, then possibly run fun"""

    box = QMessageBox(parent)
    box.setText(msg)
    box.setWindowTitle("Confirm")
    box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    result = box.exec()
    if result == QMessageBox.StandardButton.Ok:
        fun()


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
