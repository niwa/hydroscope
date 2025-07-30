import os
import sys
import pathlib
import requests
import platformdirs
import atexit
import pathlib
import platformdirs
import requests
import threading
from packaging import version
from PyQt6.QtWidgets import (
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
)
import utils
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QObject
import pathlib, platformdirs, requests, atexit, os, sys

def check_for_updates(parent):

    class VersionDialog(QDialog):
        def __init__(self, parent, cver: str, ghver: str, ivers: []):
            super().__init__(parent)
            self.setWindowTitle("Versions")

            layout = QVBoxLayout(self)
            grid = QGridLayout()
            layout.addLayout(grid)

            lab = QLabel("This version:")
            lab.setToolTip("Version of currently running program")
            grid.addWidget(lab, 0, 0)

            lab = QLabel(cver)
            lab.setToolTip("Version of currently running program")
            grid.addWidget(lab, 0, 1)

            lab = QLabel("Github code version:")
            lab.setToolTip("Version of code on github")
            grid.addWidget(lab, 1, 0)

            lab = QLabel(ghver)
            lab.setToolTip("Version of code on github")
            grid.addWidget(lab, 1, 1)


            lab = QLabel("Installable versions:")
            lab.setToolTip("Click to install this version")
            grid.addWidget(lab, 2, 0)
            for i, v in enumerate(ivers):
                # grid.addWidget(QLabel(v), i+2, 1)
                btn = QPushButton(v)
                btn.setFlat(True)  # Makes it look like a label
                btn.setStyleSheet(
                    "text-align: left; color: blue; text-decoration: underline; background: none; border: none;"
                )
                btn.clicked.connect(
                    lambda _, ver=v: possibly_update_to_version(parent, cver, ver)
                )
                grid.addWidget(btn, i + 2, 1)

            btn = QPushButton("Dismiss")
            btn.clicked.connect(self.accept)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


    cver = get_prog_version() or "unknown"
    ghver = get_github_version() or "unknown"
    ivers = get_installable_versions() or []
    dia = VersionDialog(parent, cver, ghver, ivers)
    dia.exec()

def download_version(v: str):
    """Return installer path and the done_event when download finished"""
    done_event = threading.Event()
    errors = []

    url = f"https://raw.githubusercontent.com/niwa/hydroscope/main/Output/hydroscopesetup-{v}.exe"
    ddir = pathlib.Path(platformdirs.user_downloads_dir())
    installer = ddir / f"hydroscopesetup-{v}.exe"

    def download():
        print("Starting download...", flush=True)
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(installer, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            errors.append(e)
        finally:
            done_event.set()

    thread = threading.Thread(target=download, daemon=True)
    thread.start()
    return installer, done_event, errors

def possibly_update_to_version(parent, old, new):
    """Confirm we want to update from old to new, then do it"""
    if version.parse(new) <= version.parse(old):
        m = f"Version {new} isn't newer than {old}, are you sure you want to install it?"
    else:
        m = f"Upgrade to version {new}?"

    # Start download 
    installer, done_event, errors = download_version(new)

    # see if they really want to do update
    r = QMessageBox.question(
        parent, "Update?", m, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )

    if r == QMessageBox.StandardButton.Ok:
        done_event.wait()
        if errors:
            QMessageBox.critical(parent, "Download failed", f"Unable to download update:\n{errors[0]}")
            return
        os.execl(installer, installer)


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
        return [
            ln.split("Version: ", 1)[1].strip()
            for ln in contents.splitlines()
            if ln.startswith("Version: ")
        ][0]
    except:
        return None


def get_prog_version():
    """Return version of this running program or None"""

    fname = "version.txt"
    if getattr(sys, "frozen", False):
        fname = pathlib.Path(sys._MEIPASS) / fname
    else:
        me = pathlib.Path(sys.argv[0]).resolve()
        fname = me.parent / fname

    try:
        with open(fname) as fh:
            return parse_version_txt(fh.read())
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
        v = [
            e["path"].split("-")[-1].removesuffix(".exe")
            for e in r.json()["tree"]
            if e["path"].startswith("Output/")
        ]
        return sorted(v, key=version.Version, reverse=True)
    except:
        return None

"""
def update_to_version(v: str):
    url = f"https://raw.githubusercontent.com/niwa/hydroscope/main/Output/hydroscopesetup-{v}.exe"

    ddir = pathlib.Path(platformdirs.user_downloads_dir())
    installer = ddir / f"hydroscopesetup-{v}.exe"

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(installer, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    atexit.register(os.execl, installer, installer)
    sys.exit(0)

"""
"""
class DownloadWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, version: str):
        super().__init__()
        self.version = version

    def run(self):
        try:
            url = f"https://raw.githubusercontent.com/niwa/hydroscope/main/Output/hydroscopesetup-{self.version}.exe"
            ddir = pathlib.Path(platformdirs.user_downloads_dir())
            installer = ddir / f"hydroscopesetup-{self.version}.exe"

            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(installer, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            # Queue for execl
            atexit.register(os.execl, installer, installer)
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


class DownloadDialog(QDialog):
    def __init__(self, parent, message="Downloading..."):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Please wait")

        layout = QVBoxLayout()
        self.label = QLabel(message)
        layout.addWidget(self.label)
        self.setLayout(layout)


def update_to_version(parent, version: str):
    dialog = DownloadDialog(parent)
    thread = QThread()
    worker = DownloadWorker(version)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(dialog.accept)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    worker.error.connect(lambda msg: print(f"Download error: {msg}"))
    worker.error.connect(dialog.reject)
    worker.error.connect(thread.quit)

    dialog.finished.connect(lambda _: sys.exit(0))

    thread.start()
    dialog.exec()

"""

def possibly_update(parent):
    return
