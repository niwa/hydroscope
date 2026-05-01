import pathlib
from PyQt6.QtCore import Qt, QAbstractTableModel, QRect, QEvent, QModelIndex, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QTableView,
    QWidget,
    QHeaderView,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionButton,
    QApplication,
    QStackedLayout,
    QFileDialog,
    QMessageBox,
)

import dataset


class RadioButtonDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        # Draw the cell background normally (but strip selection state)
        opt = option.__class__(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus

        # Draw base cell
        QApplication.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter
        )

        # Set up radio button option
        rb = QStyleOptionButton()
        rb.rect = self._radio_rect(option.rect)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        rb.state = QStyle.StateFlag.State_Enabled
        rb.state |= QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off

        QApplication.style().drawControl(QStyle.ControlElement.CE_RadioButton, rb, painter)

    def editorEvent(self, event, model, option, index):

        if event.type() == QEvent.Type.MouseButtonRelease:
            if self._radio_rect(option.rect).contains(event.pos()):
                model.setData(index, Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
                return True

        return False

    def _radio_rect(self, cell_rect):
        """Centre a small square within the cell for the radio button."""
        size = 16
        x = cell_rect.x() + (cell_rect.width() - size) // 2
        y = cell_rect.y() + (cell_rect.height() - size) // 2
        return QRect(x, y, size, size)


class CheckboxDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        # Draw cell background without selection/focus visuals
        opt = option.__class__(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus

        QApplication.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelItemViewItem,
            opt,
            painter,
        )

        # Configure checkbox
        cb = QStyleOptionButton()
        cb.rect = self._checkbox_rect(option.rect)

        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        cb.state = QStyle.StateFlag.State_Enabled
        cb.state |= QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off

        QApplication.style().drawControl(
            QStyle.ControlElement.CE_CheckBox,
            cb,
            painter,
        )

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            if self._checkbox_rect(option.rect).contains(event.pos()):
                current = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
                new_state = (
                    Qt.CheckState.Unchecked.value if current else Qt.CheckState.Checked.value
                )
                model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                return True

        return False

    def _checkbox_rect(self, cell_rect):
        size = 16
        x = cell_rect.x() + (cell_rect.width() - size) // 2
        y = cell_rect.y() + (cell_rect.height() - size) // 2
        return QRect(x, y, size, size)


class DatasetsPanel(QWidget):
    datasetSelected = pyqtSignal(object)

    def __init__(self, dstm, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.dstm = dstm
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Datasets")
        title.setStyleSheet("""font-size: 14px; font-weight: bold; padding: 0px;""")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.add_btn = b = QPushButton("Add")
        b.clicked.connect(self.__add_ds)
        self.remove_btn = b = QPushButton("Remove")
        b.clicked.connect(self.__del_ds)

        header_layout.addWidget(self.add_btn)
        header_layout.addWidget(self.remove_btn)

        layout.addLayout(header_layout)

        # Table
        self.table = tab = QTableView()
        self.table.setModel(self.dstm)

        header = tab.horizontalHeader()
        tab.setShowGrid(False)
        tab.verticalHeader().setVisible(False)
        tab.setColumnWidth(0, 20)
        tab.setColumnWidth(1, 20)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tab.setItemDelegateForColumn(0, CheckboxDelegate(tab))
        tab.setItemDelegateForColumn(1, RadioButtonDelegate(tab))

        tab.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        tab.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        tab.horizontalHeader().setStyleSheet(
            """
            QHeaderView::section {
                font-weight: bold;
            }
        """
        )
        tab.setStyleSheet(
            """
            QTableView {
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
                outline: 0;
            }

            QTableView::item:focus {
                outline: 0;
            }
        """
        )

        # We have the Table or a Label
        self.stack = QStackedLayout()
        placeholder = QLabel("Click Add to add a dataset")
        placeholder.setStyleSheet("""color: gray; font-size: 14px;""")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(placeholder)
        self.stack.addWidget(self.table)

        layout.addLayout(self.stack)
        self.update_view()

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def update_view(self):
        self.stack.setCurrentIndex(0 if self.dstm.rowCount() == 0 else 1)

    def __add_ds(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            self.parent.cp["DEFAULT"]["lastdir"],
            "NetCDF or CSV Files (*.nc *.csv)",
        )
        if not fname:
            return
        fname = pathlib.Path(fname)

        self.parent.cp["DEFAULT"]["lastdir"] = str(fname.parent)
        self.parent.save_config()

        guess = self.parent.cp["DEFAULT"].getboolean("guessnodata", fallback=False)

        try:
            d = dataset.Dataset(fname, guessnodata=guess)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not parse {fname}:\n{e}")
            return

        self.dstm.add_dataset(d)
        self.update_view()

    def __del_ds(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return
        row = selection[0].row()
        self.dstm.remove_dataset(row)
        self.update_view()

    def _on_selection_changed(self):
        # possibly just finished editting a dataset field
        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()

        selection = self.table.selectionModel().selectedRows()
        if not selection:
            self.datasetSelected.emit(None)
            return

        row = selection[0].row()
        ds = self.dstm.dataset(row)
        self.datasetSelected.emit(ds)


class DataSetsTableModel(QAbstractTableModel):

    datasetsChanged = pyqtSignal()
    # datasetChanged = pyqtSignal(int, object)

    def __init__(self, datasets: list):
        super().__init__()
        self._datasets = datasets
        self.columns = ["Inc", "Ref", "Name", "Variable"]
        self.col2attr = {0: "include", 1: "ref", 2: "name", 3: "var"}

    def add_dataset(self, ds):
        row = len(self._datasets)
        # first one we add gets reference by default
        if row == 0:
            ds.ref = True
        self.beginInsertRows(QModelIndex(), row, row)
        self._datasets.append(ds)
        self.endInsertRows()
        self.datasetsChanged.emit()

    def remove_dataset(self, row):
        if row < 0 or row >= len(self._datasets):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._datasets[row]
        self.endRemoveRows()
        self.datasetsChanged.emit()

    def dataset_changed(self, ds):
        try:
            row = self._datasets.index(ds)
        except Exception:
            return
        fromi = self.index(row, 2)
        toi = self.index(row, 3)
        self.dataChanged.emit(fromi, toi)

    def to_config_dicts(self):
        return [ds.to_config_dict() for ds in self._datasets]

    def dataset(self, row):
        return self._datasets[row] if 0 <= row < len(self._datasets) else None

    def rowCount(self, parent=None):
        return len(self._datasets)

    def columnCount(self, parent=None):
        return len(self.columns)

    def data(self, index, role):
        ds = self._datasets[index.row()]
        col = index.column()
        val = getattr(ds, self.col2attr[col])

        if role == Qt.ItemDataRole.TextAlignmentRole and col <= 1:
            return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.CheckStateRole and col <= 1:
            return Qt.CheckState.Checked if val else Qt.CheckState.Unchecked

        elif role == Qt.ItemDataRole.DisplayRole and col <= 3:
            return val

        return None

    def flags(self, index):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(self, index, value, role):
        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        ds = self._datasets[index.row()]
        col = index.column()

        # Include checkbox
        if col == 0:
            ds.include = value == Qt.CheckState.Checked.value
            self.dataChanged.emit(index, index)
            return True

        # Ref radio button
        elif col == 1:
            # clear all refs
            for d in self._datasets:
                d.ref = False

            # set selected row
            ds.ref = value == Qt.CheckState.Checked.value
            ds.include = True

            self.dataChanged.emit(self.index(0, 0), self.index(len(self._datasets) - 1, 1))

            return True

        return False

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section]

        return None
