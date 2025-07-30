import os
import sys
import pathlib
import requests
import platformdirs
import atexit
from packaging import version
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
    QPushButton
)
from PyQt6.QtGui import (
    QAction,
    QIcon
)
import utils

def check_for_updates(parent):

    class VersionDialog(QDialog):
        def __init__(self, parent, cver: str, ghver: str, ivers: []):
            super().__init__(parent)
            self.setWindowTitle("Versions")

            layout = QVBoxLayout(self)
            grid = QGridLayout()
            layout.addLayout(grid)


            grid.addWidget(QLabel("This version:"), 0, 0)
            grid.addWidget(QLabel(cver), 0, 1)

            grid.addWidget(QLabel("Github code version:"), 1, 0)
            grid.addWidget(QLabel(ghver), 1, 1)

            grid.addWidget(QLabel("Installable versions:"), 2, 0)
            for i, v in enumerate(ivers):
                # grid.addWidget(QLabel(v), i+2, 1)
                btn = QPushButton(v)
                btn.setFlat(True)  # Makes it look like a label
                btn.setStyleSheet("text-align: left; color: blue; text-decoration: underline; background: none; border: none;")
                btn.clicked.connect(lambda _, ver=v: possibly_update_to_version(parent, cver, ver))
                grid.addWidget(btn, i + 2, 1)

            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btns.accepted.connect(self.accept)
            layout.addWidget(btns)


    cver = get_prog_version() or 'unknown'
    ghver = get_github_version() or 'unknown'
    ivers = get_installable_versions() or []
    dia = VersionDialog(parent, cver, ghver, ivers)
    dia.exec()

def possibly_update_to_version(parent, old, new):
    """Confirm we want to update from old to new, then do it"""
    if version.parse(new) <= version.parse(old):
        m = f"Version {new} isn't newer than {old}, are you sure you want to install it?"
    else:
        m = f"Upgrade to version {new}?"
   
    utils.confirm_and_run(parent, m, lambda: update_to_version(new))


def parse_version_txt(contents):
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

def get_prog_version():
    """Return version of this running program or None"""

    fname = 'version.txt'
    if getattr(sys, "frozen", False):
        fname = pathlib.Path(sys._MEIPASS) / fname
    else:
        me = pathlib.Path(sys.argv[0]).resolve()
        fname = me.parent / fname

    try:
        with open(fname) as fh:
            return(parse_version_txt(fh.read()))
    except:
        return None
    
def get_github_version():
    url = "https://raw.githubusercontent.com/niwa/hydroscope/main/bin/version.txt"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return parse_version_txt(r.text)
    except:
        return None


def get_installable_versions():
    url = "https://api.github.com/repos/niwa/hydroscope/git/trees/main?recursive=1"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        v = [e['path'].split('-')[-1].removesuffix('.exe') for e in r.json()['tree'] if e['path'].startswith('Output/')]
        return sorted(v, key=version.Version, reverse=True)
    except:
        return None

def update_to_version(v: str):
    url = f"https://raw.githubusercontent.com/niwa/hydroscope/main/Output/hydroscopesetup-{v}.exe"

    ddir = pathlib.Path(platformdirs.user_downloads_dir())
    installer = ddir / f"hydroscope-{v}.exe"

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(installer, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    atexit.register(os.execl, installer, installer)
    sys.exit(0)

def possibly_update(parent):
    return

