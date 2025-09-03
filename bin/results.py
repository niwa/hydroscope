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
    QTableWidgetItem,
    QHeaderView,
)

from PyQt6.QtGui import (
    QRegularExpressionValidator,
    QFont
)
from PyQt6.QtCore import (
    QRegularExpression,
    Qt
)
import utils
import numpy as np
import pandas as pd
import xarray as xr
from scipy.signal import find_peaks

from permetrics.regression import RegressionMetric
from hydrosignatures.baseflow import baseflow, baseflow_index


import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas



class Results:
    def __init__(self, conf, data: pathlib.Path):
        """data is a json file of metrics and purposes."""
        self.cp = conf
        with open(data, "r") as f:
            self.p2m = json.load(f)

    # metrics
    def lognse(self, sim: pd.Series, obs: pd.Series):
        return self.nse(np.log(sim), np.log(obs))

    def nse(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return 1 - np.sum((obs - sim) ** 2) / np.sum((obs - np.mean(obs)) ** 2)

    def mae(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return np.mean(np.abs(sim - obs))

    def bias(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return np.mean(sim - obs)

    def kge(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return RegressionMetric(obs, sim).kling_gupta_efficiency()

    def pbias(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return 100 * np.sum(sim - obs) / np.sum(obs)

    def rmse(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return RegressionMetric(obs, sim).root_mean_squared_error()

    def peakrmse(self, sim: pd.Series, obs: pd.Series):
        pt = self.peak_table('', sim, obs)
        return self.rmse(pt.sim_val, pt.obs_val)

    def fdc(self, flows):
        """Return flow duration curve from

        Parameters
        ----------
        flows: np.array
            Array of values

        Returns
        -------
        df: pd.DataFrame
            Dataframe with Exceedance % and Discharge columns
        """

        sorted_discharge_values = np.sort(flows)[::-1]
        exceedence = np.arange(1.0, len(sorted_discharge_values) + 1) / len(sorted_discharge_values)

        return pd.DataFrame(
            {"Exceedence %": exceedence * 100, "Discharge (m3/s)": sorted_discharge_values}
        )

    def __bfi(self, f: np.array):
        a = float(self.cp.get('bfi_alpha', 0.925))
        n = int(self.cp.get('bfi_np', 1))
        return baseflow_index(f, alpha=a, n_passes=n) 

    def sbfi(self, sim: pd.Series, obs: pd.Series):
        return self.__bfi(sim.values)

    def obfi(self, sim: pd.Series, obs: pd.Series):
        return self.__bfi(obs.values)

    def __q95q50(self, flow: np.array):
        return np.percentile(flow, 5) / np.percentile(flow, 50)

    def sq95q50(self, sim: pd.Series, obs: pd.Series):
        return self.__q95q50(sim.values)

    def oq95q50(self, sim: pd.Series, obs: pd.Series):
        return self.__q95q50(obs.values)

    def fdc_segment_bias(self, sim: np.array, obs: np.array, lo, hi):
        qlo = np.quantile(obs, 1-hi)
        qhi = np.quantile(obs, 1-lo)
        mask = (obs >= qlo) & (obs <= qhi)
        denom =  np.nansum(obs[mask])
        return 100 * (np.nansum(sim[mask]) - np.nansum(obs[mask])) / denom if denom != 0 else np.inf

    def flv(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return self.fdc_segment_bias(sim, obs, lo=0.9, hi=1.0)

    def fhv(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        return self.fdc_segment_bias(sim, obs, lo=0, hi=0.1)

    def pte(self, sim: pd.Series, obs: pd.Series):
        """Peak timing error which is mean of timing errors in hours"""

        pt = self.peak_table('', sim, obs)
        return np.mean(np.abs(pt.obs_time.values.astype("datetime64[ns]") - pt.sim_time.astype("datetime64[ns]")) / np.timedelta64(1, "h"))

    # tables
    def peak_table(self, purp, sim: pd.Series, obs: pd.Series):
        """Return df of peaks

        Returns
        -------
        pd.DataFrame
            obs_time, obs_val, sim_time, sim_val
        """
        peak_num = int(self.cp.get('peak_num', 4))
        peak_gap = int(self.cp.get('peak_gap', 7)) * 24 * 60 * 60

        # get the timestep in seconds
        try:
            dt = (obs.index[1] - obs.index[0]).seconds
            sdt = (sim.index[1] - sim.index[0]).seconds
        except Exception as ecp:
            raise ValueError(f"Can't determine peaks, series possibly not long enough: {exp}")
        if dt != sdt:
            raise ValueError("Can only determine peaks when obs and sim have same timestep")

        # get the peaks for obs and sim
        times = []
        for s in (obs, sim):
            # indices into obs.values
            peaks, _ = find_peaks(s.values, distance=peak_gap/dt)
            # these are the top indices sorted, biggest is last
            top_peaks = peaks[np.argsort(s.values[peaks])[-peak_num:]]
            # return the actual times
            times.append(s.index[top_peaks])

        obs_time = times[0]
        sim_time = [
            times[1][np.argmin(np.abs(p -  times[1]))]
            for p in obs_time
        ]

        return pd.DataFrame({
            'obs_time': obs_time,
            'obs_val': obs[obs_time].values,
            'sim_time': sim_time,
            'sim_val': sim[sim_time].values
        })

    def metric_table(self, purp, sim: pd.Series, obs: pd.Series):
        """Return a dataframe with the metrics and their values."""
       
        # some of the metrics need the same start and end
        start = max(sim.index.min(), obs.index.min())
        end   = min(sim.index.max(), obs.index.max())
        sim = sim.loc[start:end]
        obs = obs.loc[start:end]

        mets = self.p2m[purp]['metrics']
        vals = []
        for m in mets:
            try:
                f = getattr(self, f"{m['fun']}")
            except Exception as exp:
                val = f"No {m['fun']} defined: {exp}"
            else:
                val = f(sim, obs)
            vals.append(val)

        return pd.DataFrame({'Metric': [m['name'] for m in mets], 'Value': vals})


    # graphs
    def __hydrograph(self, sim: pd.Series, obs: pd.Series, events=True):

        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        sim.plot(ax=ax, color='red')
        obs.plot(ax=ax, color='blue')
        ax.set_xlabel("Time")
        ax.set_ylabel("Flow ($m^3/s$)")
        ax.legend(['sim', 'obs'])
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment('right')

        # make a dataframe
        df = pd.DataFrame({'obs': obs, 'sim': sim}).reset_index()

        if events:
            pks = self.peak_table('', sim, obs)
            ax.scatter(pks.obs_time.values, pks.obs_val.values, color='blue', zorder=5)
            ax.scatter(pks.sim_time.values, pks.sim_val.values, color='red', zorder=5)
            for i, v in zip(pks.obs_time.values, pks.obs_val.values):
                label = pd.to_datetime(i).strftime('%Y-%m-%d')
                ax.text(i, v, label, ha='center', color='blue', va='bottom', fontsize=8, rotation=45)
            for i, v in zip(pks.sim_time.values, pks.sim_val.values):
                label = pd.to_datetime(i).strftime('%Y-%m-%d')
                ax.text(i, v, label, ha='center', color='red', va='bottom', fontsize=8, rotation=45)

            df['obs_event'] = df.time.isin(pks.obs_time.values)
            df['sim_event'] = df.time.isin(pks.sim_time.values)

        return (df, fig)

    def hydrograph(self, sim: pd.Series, obs: pd.Series):
        return self.__hydrograph(sim, obs, events=False)

    def hydrograph_with_events(self, sim: pd.Series, obs: pd.Series):
        return self.__hydrograph(sim, obs, events=True)

    def flow_duration_curve(self, sim: pd.Series, obs: pd.Series):
        """Return flow duration curve from

        Returns
        -------
        df: pd.DataFrame
            Dataframe with Exceedance % and Discharge columns
        """
        
        sfdc = self.fdc(sim.values)
        ofdc = self.fdc(obs.values)

        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        sfdc.plot(x="Exceedence %", y="Discharge (m3/s)", ax=ax, color="red")#, legend='sim')
        ofdc.plot(x="Exceedence %", y="Discharge (m3/s)", ax=ax, color="blue")#, legend='obs')
        ax.set_xlabel("Exceedence %")
        ax.set_ylabel("Discharge (m³/s)")
        ax.legend(['sim', 'obs'])

        df = pd.concat([sfdc.set_index("Exceedence %"), ofdc.set_index("Exceedence %")], axis=1).reset_index()
        df.columns = ["Exceedence %", "sim flow", "obs flow"]

        return (df, fig)

    def make_sine(self, sim, obs):
        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        x = np.linspace(0, 10, 400)
        ax.plot(x, np.sin(x))
        ax.set_title("Sine")
        return (pd.DataFrame(), fig)

    def make_scatter(self, sim, obs):
        fig = matplotlib.figure.Figure(constrained_layout=True)
        ax = fig.add_subplot(111)
        rng = np.random.default_rng(0)
        x, y = rng.normal(size=200), rng.normal(size=200)
        ax.scatter(x, y)
        ax.set_title("Scatter")
        return (pd.DataFrame(), fig)

    def get_tables(self, purp, sim, obs):
        dfs = []
        for t in self.p2m[purp]['tables']:
            try:
                f = getattr(self, f"{t['fun']}")
            except Exception as exp:
                print(exp)
                val = pd.DataFrame([[f"No {t['fun']} defined: {exp}"]])
            else:
                val = f(purp, sim, obs)
            dfs.append(val)

        ret = []
        for tab, df in zip(self.p2m[purp]['tables'], dfs):
            table = QTableWidget()
            table.setRowCount(df.shape[0])
            table.setColumnCount(df.shape[1])
            table.verticalHeader().setVisible(False)

            table.setHorizontalHeaderLabels(df.columns)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            font = QFont()
            font.setBold(True)
            header.setFont(font)

            for i in range(df.shape[0]):
                for j in range(df.shape[1]):
                    value = df.iloc[i, j]
                    if isinstance(value, float):
                        text = f"{value:.4g}"   # 3sf
                    elif isinstance(value, (int, str)):
                        text = str(value)
                    else:
                        text = "" if pd.isna(value) else str(value)

                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # make non-editable
                    table.setItem(i, j, item)

            ret.append((tab['name'], df, table))
        
        return(ret)

    def get_graphs(self, purp, sim, obs):
        graphs = self.p2m[purp]['graphs']
        ret = []
        for g in graphs:
            try:
                f = getattr(self, f"{g['fun']}")
            except Exception as exp:
                val = [pd.DataFrame(), matplotlib.figure.Figure(constrained_layout=True)]
            else:
                val = f(sim, obs)
            ret.append([g['name'], val[0], val[1]])
        return ret



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

