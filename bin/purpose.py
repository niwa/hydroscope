import pathlib
import json
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QGroupBox, QPushButton


class PurposeWidget(QGroupBox):

    def __init__(self, title: str, data: pathlib.Path, parent):
        """data is a json file of metrics and purposes."""
        super().__init__(title)
        self.parent = parent
        with open(data, "r") as f:
            self.purps = list(json.load(f)["purpose"].keys())
        self.init_ui()

    def init_ui(self):
        hbox = QHBoxLayout(self)

        # Purpose label and dropdown
        hbox.addWidget(QLabel("Purpose:"))
        self.purpose_cb = pcb = QComboBox()
        pcb.addItems(self.purps)
        if self.parent.cp["DEFAULT"].get("purpose") in self.purps:
            pcb.setCurrentText(self.parent.cp["DEFAULT"].get("purpose"))
        pcb.currentTextChanged.connect(self.purpose_changed)
        hbox.addWidget(pcb)

        hbox.addStretch()

        # calculate button
        btn = QPushButton("Calculate")
        btn.clicked.connect(self.calculate)
        hbox.addWidget(btn)

    def purpose_changed(self):
        p = self.purpose_cb.currentText()
        self.parent.cp["DEFAULT"]["purpose"] = p

    def calculate(self):
        p = self.purpose_cb.currentText()
        self.parent.calculate(p)
