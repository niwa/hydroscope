import pathlib
import json
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QGroupBox, QPushButton


class MetricsWidget(QGroupBox):

    def __init__(self, title: str, data: pathlib.Path, parent):
        """data is a json file of metrics and purposes."""
        super().__init__(title)
        self.parent = parent
        with open(data, "r") as f:
            self.p2m = json.load(f)["purpose"]
        self.init_ui()

    def init_ui(self):
        hbox = QHBoxLayout(self)

        # Purpose label and dropdown
        hbox.addWidget(QLabel("Purpose:"))
        self.purpose_cb = pcb = QComboBox()
        pcb.addItems(list(self.p2m.keys()))
        if self.parent.cp["DEFAULT"].get("purpose") in self.p2m.keys():
            pcb.setCurrentText(self.parent.cp["DEFAULT"].get("purpose"))
        pcb.currentTextChanged.connect(self.purpose_changed)
        hbox.addWidget(pcb)

        # Metrics box
        hbox.addWidget(QLabel("Metric:"))
        self.metric_cb = mcb = QComboBox()
        hbox.addWidget(mcb)

        # set the allowable metrics
        itms = self.p2m[self.purpose_cb.currentText()]
        mcb.addItems(itms)
        if self.parent.cp["DEFAULT"].get("metric") in itms:
            mcb.setCurrentText(self.parent.cp["DEFAULT"].get("metric"))

        # now can add this, otherwise it would have overriden the saved one
        mcb.currentTextChanged.connect(self.metric_changed)

        hbox.addStretch()

        # calculate button
        btn = QPushButton("Calculate")
        btn.clicked.connect(self.calculate)
        hbox.addWidget(btn)

    def purpose_changed(self):
        self.metric_cb.clear()
        p = self.purpose_cb.currentText()
        self.parent.cp["DEFAULT"]["purpose"] = p
        self.metric_cb.addItems(self.p2m[p])

    def metric_changed(self):
        m = self.metric_cb.currentText()
        self.parent.cp["DEFAULT"]["metric"] = m

    def calculate(self):
        m = self.metric_cb.currentText()
        self.parent.calculate(m)
