import pathlib
import json
import numpy as np
import pandas as pd
import matplotlib
from scipy.signal import find_peaks
from permetrics.regression import RegressionMetric
from hydrosignatures.baseflow import baseflow_index

matplotlib.use("QtAgg")
import matplotlib.figure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)

from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QMessageBox,
    QComboBox,
    QStackedWidget,
)


class Results:
    def __init__(self, conf, data: pathlib.Path):
        """data is a json file of metrics and purposes."""
        self.cp = conf
        with open(data, "r") as f:
            self.p2m = json.load(f)

    # metrics
    def lognse(self, sim: pd.Series, obs: pd.Series):
        if (sim <= 0).any() or (obs <= 0).any():
            return np.nan
        return self.nse(np.log(sim), np.log(obs))

    # FIXME, check getting overflow but denom!=0
    def nse(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        denom = np.sum((obs - np.mean(obs)) ** 2)
        return (1 - np.sum((obs - sim) ** 2) / denom) if denom != 0 else np.inf

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
        return 100 * np.sum(sim - obs) / np.sum(obs) if np.sum(obs) != 0 else np.inf

    def rmse(self, sim: pd.Series, obs: pd.Series):
        obs = obs.values
        sim = sim.values
        if len(obs) == len(sim) == 0:
            return np.nan
        return RegressionMetric(obs, sim).root_mean_squared_error()

    def peakrmse(self, sim: pd.Series, obs: pd.Series):
        pt = self.peak_table("", [sim], obs)
        return self.rmse(pt[f"{sim.name}_val"], pt.obs_val)

    def __bfi(self, f: np.array):
        a = float(self.cp.get("bfi_alpha", 0.925))
        n = int(self.cp.get("bfi_np", 1))
        return baseflow_index(f, alpha=a, n_passes=n)

    def sbfi(self, sim: pd.Series, obs: pd.Series):
        return self.__bfi(sim.values)

    def obfi(self, sim: pd.Series, obs: pd.Series):
        return self.__bfi(obs.values)

    def __q95q50(self, flow: np.array):
        denom = np.percentile(flow, 50)
        return np.percentile(flow, 5) / denom if denom != 0 else np.inf

    def sq95q50(self, sim: pd.Series, obs: pd.Series):
        return self.__q95q50(sim.values)

    def oq95q50(self, sim: pd.Series, obs: pd.Series):
        return self.__q95q50(obs.values)

    def fdc_segment_bias(self, sim: np.array, obs: np.array, lo, hi):
        qlo = np.quantile(obs, 1 - hi)
        qhi = np.quantile(obs, 1 - lo)
        mask = (obs >= qlo) & (obs <= qhi)
        denom = np.nansum(obs[mask])
        return (
            100 * (np.nansum(sim[mask]) - np.nansum(obs[mask])) / denom if denom != 0 else np.inf
        )

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

        pt = self.peak_table("", [sim], obs)
        return np.mean(
            np.abs(
                pt.obs_time.values.astype("datetime64[ns]")
                - pt[f"{sim.name}_time"].astype("datetime64[ns]")
            )
            / np.timedelta64(1, "h")
        )

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
        exceedence = np.arange(1.0, len(sorted_discharge_values) + 1) / len(
            sorted_discharge_values
        )

        return pd.DataFrame(
            {"Exceedence %": exceedence * 100, "Discharge (m3/s)": sorted_discharge_values}
        )

    # tables
    def peak_table(self, purp, sims: pd.Series, obs: pd.Series):
        """Return df of peaks

        Returns
        -------
        pd.DataFrame
            obs_time, obs_val, sim_time, sim_val
        """
        peak_num = int(self.cp.get("peak_num", 4))
        peak_gap = int(self.cp.get("peak_gap", 7)) * 24 * 60 * 60

        # get the timestep in seconds
        try:
            dt = (obs.index[1] - obs.index[0]).total_seconds()
        except Exception as exp:
            raise ValueError(f"Can't determine peaks, series possibly not long enough: {exp}")
        try:
            sdts = [(s.index[1] - s.index[0]).total_seconds() for s in sims]
        except Exception as exp:
            raise ValueError(f"Can't determine peaks, series possibly not long enough: {exp}")
        if not all(sdt == dt for sdt in sdts):
            raise ValueError("Can only determine peaks when obs and sims have same timestep")

        if peak_gap <= dt:
            raise ValueError("Can't demtermine peaks, aggregated series possibly not long enough")

        # get the peaks for obs and the sims
        # times[0] list of obs peaks
        # times[1] list of peaks for first sim
        # etc
        times = []
        for s in [obs] + sims:
            # indices into obs.values
            peaks, _ = find_peaks(s.values, distance=peak_gap / dt)
            # these are the top indices sorted, biggest is last
            top_peaks = peaks[np.argsort(s.values[peaks])[-peak_num:]]
            # return the actual times
            times.append(s.index[top_peaks])

        if any(len(t) == 0 for t in times):
            return pd.DataFrame(
                {
                    "obs_time": [],
                    "obs_val": [],
                    "sim_time": [],
                    "sim_val": [],
                }
            )

        obs_time = times[0]
        data = {
            "obs_time": obs_time,
            "obs_val": obs[obs_time].values,
        }

        for sim, sim_times in zip(sims, times[1:]):
            st = [sim_times[np.argmin(np.abs(p - sim_times))] for p in obs_time]
            data[f"{sim.name}_time"] = st
            data[f"{sim.name}_val"] = sim[st].values

        df = pd.DataFrame(data)

        return df

    def metric_table(self, purp, sims: pd.Series, obs: pd.Series):
        """Return a dataframe with the metrics and their values."""

        # some of the metrics need the same start and end
        start = max(max(s.index.min() for s in sims), obs.index.min())
        end = min(min(s.index.max() for s in sims), obs.index.max())
        sims = [s.loc[start:end] for s in sims]
        obs = obs.loc[start:end]

        if start >= end:
            return pd.DataFrame({"Error": ["Not enough overlapping data"]})

        mets = self.p2m[purp]["metrics"]
        vals = {}
        for s in sims:
            vs = []
            for m in mets:
                try:
                    f = getattr(self, f"{m['fun']}")
                except Exception as exp:
                    v = f"No {m['fun']} defined: {exp}"
                else:
                    try:
                        v = f(s, obs)
                    except Exception as exp:
                        v = f"{exp}"
                vs.append(v)
            vals[s.name] = vs
        data = {"Metric": [m["name"] for m in mets]}
        data.update(vals)
        return pd.DataFrame(data)

    # graphs
    def __hydrograph(
        self, sims: list[pd.Series], obs: pd.Series, simunits, obsunits, events=True
    ):
        fig = matplotlib.figure.Figure()  # constrained_layout=True)
        cmap = plt.get_cmap("tab10")
        ax = fig.add_subplot(111)

        def plot(s, ax, **k):
            ax.plot(s.index, s.values, marker="o", **k) if len(s) <= 1 else s.plot(ax=ax, **k)

        sim_colours = {}
        plot(obs, ax, color="blue", label=obs.name or "", legend=False)
        for i, sim in enumerate(sims):
            sim_colours[sim.name or f"sim{i}"] = cmap(i)
            plot(sim, ax, color=cmap(i), label=sim.name or "", legend=False)

        xmin = min([obs.index.min()] + [s.index.min() for s in sims])
        xmax = max([obs.index.max()] + [s.index.max() for s in sims])
        if xmax > xmin:
            ax.set_xlim(xmin, xmax)
        ax.set_xlabel("Time")

        # y axis can only contain units since names never match
        units = [u for u in [obsunits] + simunits if u is not None]
        if len(units) > 0 and all(u == units[0] for u in units):
            ax.set_ylabel(units[0])

        # x ticks rotate
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment("right")

        ax.legend()

        # make a dataframe
        df = pd.DataFrame({"obs": obs})
        for s in sims:
            name = s.name or "sim"
            df[name] = s
        df = df.reset_index()

        if events:
            try:
                pks = self.peak_table("", sims, obs)

                # put the obs in
                ax.scatter(pks.obs_time.values, pks.obs_val.values, color="blue", zorder=5)
                for i, v in zip(pks.obs_time.values, pks.obs_val.values):
                    label = pd.to_datetime(i).strftime("%Y-%m-%d")
                    ax.text(
                        i,
                        v,
                        label,
                        ha="center",
                        color="blue",
                        va="bottom",
                        fontsize=8,
                        rotation=45,
                    )
                df["obs_event"] = df.time.isin(pks.obs_time.values)

                # and each sim
                for i, sim in enumerate(sims):
                    name = sim.name or f"sim{i}"
                    tcol = f"{name}_time"
                    vcol = f"{name}_val"
                    colour = sim_colours.get(name, "red")

                    if tcol not in pks or vcol not in pks:
                        continue

                    ax.scatter(pks[tcol].values, pks[vcol].values, color=colour, zorder=5)
                    for t, v in zip(pks[tcol].values, pks[vcol].values):
                        label = pd.to_datetime(t).strftime("%Y-%m-%d")
                        ax.text(
                            t,
                            v,
                            label,
                            ha="center",
                            color=colour,
                            va="bottom",
                            fontsize=8,
                            rotation=45,
                        )

                    df[f"{name}_event"] = df["time"].isin(pks[tcol].values)

            except Exception as exp:
                ax.text(0.5, 0.5, exp, transform=ax.transAxes, ha="center", va="center")

        fig.tight_layout()
        return (df, fig)

    def hydrograph(self, sim: pd.Series, obs: pd.Series, simunits, obsunits):
        return self.__hydrograph(sim, obs, simunits, obsunits, events=False)

    def hydrograph_with_events(self, sim: pd.Series, obs: pd.Series, simunits, obsunits):
        return self.__hydrograph(sim, obs, simunits, obsunits, events=True)

    def flow_duration_curve(self, sims: list[pd.Series], obs: pd.Series, simunits, obsunits):
        """Return flow duration curve from

        Returns
        -------
        df: pd.DataFrame
            Dataframe with Exceedance % and Discharge columns
        """

        fig = matplotlib.figure.Figure()
        ax = fig.add_subplot(111)

        ofdc = self.fdc(obs.values)
        ofdc.plot(
            x="Exceedence %",
            y="Discharge (m3/s)",
            ax=ax,
            color="blue",
            linewidth=2,
            label=obs.name or "Ref",
            legend=False,
        )

        sim_fdcs = []
        for sim in sims:
            sfdc = self.fdc(sim.values)
            sim_fdcs.append((sim, sfdc))
            sfdc.plot(
                x="Exceedence %",
                y="Discharge (m3/s)",
                ax=ax,
                label=sim.name or "Sim",
                legend=False,
            )

        ax.set_xlabel("Exceedence %")

        # y axis can only contain units since names never match
        units = [u for u in [obsunits] + simunits if u is not None]
        if len(units) > 0 and all(u == units[0] for u in units):
            ax.set_ylabel(units[0])

        ax.legend()

        df = ofdc.set_index("Exceedence %").rename(
            columns={"Discharge (m3/s)": f"{obs.name or 'Ref'}"}
        )
        for sim, sfdc in sim_fdcs:
            df = df.join(
                sfdc.set_index("Exceedence %").rename(
                    columns={"Discharge (m3/s)": f"{sim.name or 'Sim'} flow"}
                )
            )

        df = df.reset_index()
        fig.tight_layout()
        return (df, fig)

    def get_tables(self, purp, sims, obs):

        dfs = []
        for t in self.p2m[purp]["tables"]:
            try:
                f = getattr(self, f"{t['fun']}")
            except Exception as exp:
                val = pd.DataFrame({"Error": [f"No {t['fun']} defined: {exp}"]})
            else:
                try:
                    val = f(purp, sims, obs)
                except Exception as exp:
                    val = pd.DataFrame({"Error": [f"{exp}"]})
            dfs.append(val)

        ret = []
        for tab, df in zip(self.p2m[purp]["tables"], dfs):
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
                        text = f"{value:.4g}"  # 3sf
                    else:
                        text = str(value)

                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # make non-editable
                    table.setItem(i, j, item)

            ret.append((tab["name"], df, table))

        return ret

    def get_graphs(self, purp, sims, obs, simunits, obsunits):
        graphs = self.p2m[purp]["graphs"]
        ret = []
        for g in graphs:
            try:
                f = getattr(self, f"{g['fun']}")
            except Exception:
                val = [pd.DataFrame(), matplotlib.figure.Figure(constrained_layout=True)]
            else:
                try:
                    val = f(sims, obs, simunits, obsunits)
                except Exception:
                    val = [pd.DataFrame(), matplotlib.figure.Figure(constrained_layout=True)]
            ret.append([g["name"], val[0], val[1]])
        return ret


class ResultsWidget(QGroupBox):

    def __init__(self, rd: Results, title="Results", parent=None):
        super().__init__(title, parent=parent)
        self.results = rd
        self.title = title
        self.parent = parent
        self.init_ui()
        self.setMinimumSize(500, 500)

    def __get_ts(self, idx):
        """Return the timestep in seconds for an index without using infer"""
        diffs = idx.to_series().diff().dropna().dt.total_seconds()
        if len(diffs):
            return diffs.median()
        return None

    def calculate(self, purpose, models, obs, munits, ounits, magg, oagg):
        """models is a list of series"""

        self.clear_tabs()

        if self.results.cp.getboolean("aggregation", fallback=False):
            m_ts = [self.__get_ts(m.index) for m in models]
            o_ts = self.__get_ts(obs.index)
            if any(t is None for t in m_ts):
                QMessageBox.warning(
                    self, "Timestep error", "Cannot work out timestep for a model"
                )
                return
            if o_ts is None:
                QMessageBox.warning(
                    self, "Timestep error", "Cannot work out timestep for reference model"
                )
                return

            max_ts = o_ts
            max_source = obs
            for m, ts in zip(models, m_ts):
                if ts > max_ts:
                    max_ts = ts
                    max_source = m
            freq = pd.infer_freq(max_source.index)
            if freq is None:
                freq = "1H"

            for i, (m, ts, ma) in enumerate(zip(models, m_ts, magg)):
                # only aggregate if enough difference in timesteps
                if ts < max_ts - 1:
                    models[i] = m.resample(freq).agg(ma)
            if o_ts < max_ts - 1:
                obs = obs.resample(freq).agg(oagg)

        # possibly not enough data left if we did aggregation
        if any(len(m) < 3 for m in models):
            QMessageBox.warning(
                self, "Data error", "Not enough model data to calculate statistics"
            )
            return
        if len(obs) < 3:
            QMessageBox.warning(self, "Data error", "Not enough obs data to calculate statistics")
            return

        # scales is {"original", None, "daily": "D", "monthly": "ME" etc}
        m_ts = [self.__get_ts(m.index) for m in models]
        o_ts = self.__get_ts(obs.index)
        scales = self.__get_scales_for_series(max(max(m_ts), o_ts))

        # build the figure data
        numoffigs = len(self.results.p2m[purpose]["graphs"])
        names = [{} for _ in range(numoffigs)]
        dfs = [{} for _ in range(numoffigs)]
        figs = [{} for _ in range(numoffigs)]
        for label, agg in scales.items():
            ms = (
                models
                if agg is None
                else [m.resample(f"{agg}").agg(ma) for m, ma in zip(models, magg)]
            )
            o = obs if agg is None else obs.resample(f"{agg}").agg(oagg)
            for i, (name, df, fig) in enumerate(
                self.results.get_graphs(purpose, ms, o, munits, ounits)
            ):
                names[i][label] = name
                dfs[i][label] = df
                figs[i][label] = fig

        for name, df, fig in zip(names, dfs, figs):
            wid = TimescaleFigureTab(name, df, fig)
            i = self.tabs.addTab(wid, next(iter(name.values())))
            self.tabs.tabBar().setTabData(i, df)

        # build table data
        numoftables = len(self.results.p2m[purpose]["tables"])
        # a list of tables, each element is a dict of timescale to results
        names = [{} for _ in range(numoftables)]
        dfs = [{} for _ in range(numoftables)]
        datas = [{} for _ in range(numoftables)]
        for label, agg in scales.items():
            ms = (
                models
                if agg is None
                else [m.resample(f"{agg}").agg(ma) for m, ma in zip(models, magg)]
            )
            o = obs if agg is None else obs.resample(f"{agg}").agg(oagg)
            for i, ndd in enumerate(self.results.get_tables(purpose, ms, o)):
                names[i][label] = ndd[0]
                dfs[i][label] = ndd[1]
                datas[i][label] = ndd[2]

        for name, df, data in zip(names, dfs, datas):
            wid = TimescaleTableTab(name, df, data)
            i = self.tabs.addTab(wid, next(iter(name.values())))
            self.tabs.tabBar().setTabData(i, df)

        self.dl_btn.setEnabled(True)

    def __get_scales_for_series(self, ts):
        ye = self.results.cp.get("lastmonthofyear", "Dec").upper()
        SCALE_ORDER = [
            ("daily", "D", 86400),
            ("monthly", "ME", 86400 * 28),
            ("seasonal", f"QE-{ye}", 86400 * 90),
            ("yearly", f"YE-{ye}", 86400 * 365),
        ]
        scales = {"original": None}
        if ts is not None:
            for label, freq, secs in SCALE_ORDER:
                if secs > ts:
                    scales[label] = freq
        return scales

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

        tab_text = self.tabs.tabText(i)
        fname = f"{tab_text}.csv"

        if isinstance(df, dict):
            widget = self.tabs.widget(i)
            ts = widget.combo.currentText() if hasattr(widget, "combo") else None
            fname = f"{tab_text}_{ts}.csv" if ts in df else f"{tab_text}.csv"
            df = df.get(ts, next(iter(df.values())))

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", fname, "CSV Files (*.csv)")
        if path:
            df.to_csv(path, index=False)


class TimescaleTableTab(QWidget):
    def __init__(self, names_dict, dfs_dict, datas_dict, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # combobox for each timescale
        hbox = QHBoxLayout()
        self.combo = QComboBox()
        scales = list(names_dict.keys())
        self.combo.addItems(scales)
        hbox.addStretch()
        hbox.addWidget(self.combo)
        layout.addLayout(hbox)

        # stack the table widgets (one per timescale), only show one
        self.tables = {}
        for scale, widget in datas_dict.items():
            layout.addWidget(widget)
            widget.setVisible(False)
            self.tables[scale] = widget

        # Show the first scale by default
        first_scale = scales[0]
        self.tables[first_scale].setVisible(True)

        # switch visible table on combo change
        self.combo.currentTextChanged.connect(self.on_scale_changed)

        self.setLayout(layout)

    def on_scale_changed(self, scale):
        for s, widget in self.tables.items():
            widget.setVisible(s == scale)


class TimescaleFigureTab(QWidget):
    def __init__(self, names: dict, dfs: dict, figs: dict, parent=None):
        super().__init__(parent)

        self.names = names
        self.dfs = dfs
        self.figs = figs

        main_layout = QVBoxLayout(self)

        hbox = QHBoxLayout()
        self.combo = QComboBox()
        scales = list(names.keys())
        self.combo.addItems(scales)
        hbox.addStretch()
        hbox.addWidget(self.combo)
        main_layout.addLayout(hbox)

        # --- stacked widget for figures
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # create each figure page
        for ts, fig in figs.items():
            container = QWidget()
            layout = QHBoxLayout(container)

            canvas = FigureCanvas(fig)

            toolbar = NavigationToolbar(canvas, self)
            toolbar.setOrientation(Qt.Orientation.Vertical)
            toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            toolbar.setMaximumWidth(40)
            toolbar.setMinimumWidth(40)

            for action in toolbar.actions():
                if action.text() in ("Subplots", "Customize"):
                    toolbar.removeAction(action)

            layout.addWidget(canvas)
            layout.addWidget(toolbar)

            self.stack.addWidget(container)

        self.combo.currentIndexChanged.connect(self.stack.setCurrentIndex)
