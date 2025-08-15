import pathlib
import json
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QGroupBox


class MetricsWidget(QGroupBox):

    def __init__(self, title: str, data: pathlib.Path):
        """data is a json file of metrics and purposes."""
        super().__init__(title)
        with open(data, "r") as f:
            self.p2m = json.load(f)
        self.init_ui()

    def init_ui(self):
        hbox = QHBoxLayout(self)

        # Purpose label and dropdown
        hbox.addWidget(QLabel("Purpose:"))
        self.purpose_cb = pcb = QComboBox()
        pcb.addItems(list(self.p2m.keys()))
        hbox.addWidget(pcb)

        title = QLabel("blahdfsfds")
        hbox.addWidget(title)
