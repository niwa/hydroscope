import re
import pathlib
import json
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QTextEdit,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem
)

from PyQt6.QtGui import (
    QRegularExpressionValidator,
)
from PyQt6.QtCore import (
    QRegularExpression,
    Qt
)
import utils
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas



class Results:
    def __init__(self, data: pathlib.Path):
        """data is a json file of metrics and purposes."""
        with open(data, "r") as f:
            j = json.load(f)
            self.p2m = j['purpose']
            self.mets = j['metric']

    def nse(self, sim: np.array, obs: np.array):
        return 1 - np.sum((obs - sim) ** 2) / np.sum((obs - np.mean(obs)) ** 2)

    def mae(self, sim: np.array, obs: np.array):
        return np.mean(np.abs(sim - obs))

    def bias(self, sim: np.array, obs: np.array):
        return np.mean(sim - obs)

    def calc_metric(self, met, model, obs):
        try:
            m = getattr(self, self.mets[met]['method'])
        except Exception as exp:
            return f"No {self.mets[met]['method']} defined: {exp}"
        return m(model, obs)

    def make_sine(self):
        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        x = np.linspace(0, 10, 400)
        ax.plot(x, np.sin(x))
        ax.set_title("Sine")
        return fig

    def make_scatter(self):
        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        rng = np.random.default_rng(0)
        x, y = rng.normal(size=200), rng.normal(size=200)
        ax.scatter(x, y)
        ax.set_title("Scatter")
        return fig

    def get_tables(self, purp, model, obs):
        mets = list(self.p2m[purp])
        res = [self.calc_metric(m, model, obs) for m in mets]
        df = pd.DataFrame({'Metric': mets, 'Value': res})

        table = QTableWidget()
        table.setRowCount(df.shape[0])
        table.setColumnCount(df.shape[1])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)

        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                item = QTableWidgetItem(str(df.iloc[i, j]))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # make non-editable
                table.setItem(i, j, item)

        return [(f'Metrics', df, table)]

    def get_graphs(self, purp, model, obs):
        dfs = pd.DataFrame({"x": np.linspace(0, 10, 100), "y": np.sin(np.linspace(0, 10, 100))})
        dfc = pd.DataFrame({"x": np.linspace(0, 10, 100), "y": np.random.rand(100)})
        return [('FDC', dfs, self.make_sine()), ('Blah', dfc, self.make_scatter())]


class ResultsWidget(QGroupBox):

    def __init__(self, rd: Results, title='Results', parent=None):
        super().__init__(title, parent=parent)
        self.results = rd
        self.title = title
        self.parent = parent
        self.init_ui()
        self.setMinimumSize(400, 400)

    def calculate(self, purpose, model, obs):
        self.clear_tabs()

        # figures
        for name, df, fig in self.results.get_graphs(purpose, model, obs):
            i = self.tabs.addTab(FigureCanvas(fig), name)
            self.tabs.tabBar().setTabData(i, df)

        # tables
        for name, df, data in self.results.get_tables(purpose, model, obs):
            i = self.tabs.addTab(data, name)
            self.tabs.tabBar().setTabData(i, df)


        self.dl_btn.setEnabled(True)

    def clear_tabs(self):
        while self.tabs.count() > 0:
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()

    def init_ui(self):
        vbox = QVBoxLayout(self)

        # For the plots and txt table
        self.tabs = tabs = QTabWidget(self)
        vbox.addWidget(tabs)

        # Download button
        hbox = QHBoxLayout()
        hbox.addStretch()
        self.dl_btn = btn = QPushButton("Download")
        btn.clicked.connect(self.download_current_df)
        btn.setEnabled(False)
        hbox.addWidget(btn)

        vbox.addLayout(hbox)


    def download_current_df(self):
        i = self.tabs.currentIndex()
        df = self.tabs.tabBar().tabData(i)
        if df is None:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", f"{self.tabs.tabText(i)}.csv", "CSV Files (*.csv)")
        if path:
            df.to_csv(path, index=False)

