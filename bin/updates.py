import os
import sys
import pathlib
import requests
import platformdirs
import threading
from packaging import version
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
)


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
            for i, vnu in enumerate(ivers):
                # grid.addWidget(QLabel(v), i+2, 1)
                btn = QPushButton(vnu['version'])
                btn.setFlat(True)  # Makes it look like a label
                btn.setStyleSheet(
                    "text-align: left; color: blue; text-decoration: underline; background: none; border: none;"
                )
                btn.clicked.connect(
                    lambda _, vnu=vnu: possibly_update_to_version(parent, "Update?", cver, vnu)
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


def download_version(vnu: dict):
    """Return installer path and the done_event when download finished

    Parameters
    ----------
    vnu: dict
        {'version', 'name', 'url'}

    """
    done_event = threading.Event()
    errors = []

    ddir = pathlib.Path(platformdirs.user_downloads_dir())
    installer = ddir / vnu['name']

    def download():
        try:
            with requests.get(vnu['url'], stream=True) as r:
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


def possibly_update_to_version(parent, title, old, new):
    """Confirm we want to update from old to new, then do it"""

    if version.parse(new['version']) <= version.parse(old):
        m = f"Version {new['version']} isn't newer than {old}, are you sure you want to install it?"
    else:
        m = f"Upgrade to version {new['version']}?"

    # Start download
    installer, done_event, errors = download_version(new)

    # see if they really want to do update
    r = QMessageBox.question(
        parent, title, m, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )

    if r == QMessageBox.StandardButton.Ok:
        done_event.wait()
        if errors:
            QMessageBox.critical(
                parent, "Download failed", f"Unable to download update:\n{errors[0]}"
            )
            return
        os.execl(installer, installer)


def possibly_update(parent):
    cver = get_prog_version()
    ivers = get_installable_versions()
    if not (cver and ivers) or version.parse(cver) >= version.parse(ivers[0]['version']):
        return
    possibly_update_to_version(parent, "New version available", cver, ivers[0])


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
    except Exception:
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
    except Exception:
        return None


def get_github_version():
    url = "https://raw.githubusercontent.com/niwa/hydroscope/main/bin/version.txt"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return parse_version_txt(r.text)
    except Exception:
        return None

def get_installable_versions():
    """Return a sorted list of [{'version': version, 'name': name, 'url': url}]"""

    url = f"https://api.github.com/repos/niwa/hydroscope/releases"
    headers = {"Accept": "application/vnd.github+json"}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        releases = []
        for release in r.json():
            releases.append({
                'version': release["tag_name"],
                'name':  release["assets"][0]["name"],
                'url': release["assets"][0]["browser_download_url"]
            })
    except Exception:
        return []

    return sorted(releases, key=lambda i: version.Version(i['version']), reverse=True)
