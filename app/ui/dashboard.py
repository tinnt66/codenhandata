import csv
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QSpacerItem, QFrame, QMessageBox
)

from ..config import (
    ADXL_BATCH_SIZE,
    ADXL_FLUSH_INTERVAL_S,
    ADXL_HEADERS,
    API_KEY,
    CSV_AUTO_DIR,
    DEVICE_ID,
    ID_TEMP_HUM,
    ID_WIND_DIR,
    ID_WIND_SPD,
    MAX_SAMPLES,
    READ_INTERVAL_MS,
    SERVER_URL,
    TABLE_HEADERS,
)
from ..realtime_sender import RealtimeSender
from ..sensors.adxl import ADXLLogger
from ..sensors.rs485 import deg_to_cardinal, make_instrument
from .plots import SimplePlot


# ================= MAIN DASHBOARD ==================
class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sensor Manager (RS485_ADXL345)")
        self.resize(1450, 860)

        self.inst_temp = make_instrument(ID_TEMP_HUM)
        self.inst_dir = make_instrument(ID_WIND_DIR)
        self.inst_spd = make_instrument(ID_WIND_SPD)

        self.data_times = []
        self.data_temp = []
        self.data_hum = []
        self.data_wdir_deg = []
        self.data_wspd = []

        # ===== ADXL logger handle =====
        self.adxl_logger = None
        self.adxl_csv_path = None

        # ===== ADD: realtime sender handle =====
        self.rt_sender = None

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # Topbar buttons
        topbar = QHBoxLayout()
        self.btnExportExcelADXL = QPushButton("Export Excel ADXL345")
        self.btnExportExcelRS485 = QPushButton("Export Excel RS485")
        self.btnStart = QPushButton("Start")
        self.btnStop = QPushButton("Stop"); self.btnStop.setEnabled(False)
        self.btnRefresh = QPushButton("Refresh")
        self.btnExportExcelADXL.clicked.connect(self.export_excel_adxl_dialog)
        self.btnExportExcelRS485.clicked.connect(self.export_excel_rs485_dialog)
        self.btnStart.clicked.connect(self.start_reading)
        self.btnStop.clicked.connect(self.stop_reading)
        self.btnRefresh.clicked.connect(self.redraw_plots)
        topbar.addWidget(self.btnExportExcelADXL)
        topbar.addWidget(self.btnExportExcelRS485)
        topbar.addWidget(self.btnStart)
        topbar.addWidget(self.btnStop)
        topbar.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        topbar.addWidget(self.btnRefresh)
        main.addLayout(topbar)

        # === Tiles Layout ===
        tiles_layout = QHBoxLayout(); tiles_layout.setSpacing(12)
        self.tile_temp = self._tile_unified("Temperature", "°C", "#00cc66")
        self.tile_hum = self._tile_unified("Humidity", "%", "#4da6ff")
        self.tile_wdir = self._tile_unified("Wind Direction", "", "#ff9a33", with_subline=True)
        self.tile_wspd = self._tile_unified("Wind Speed", "m/s", "#ffcc00")
        # ADXL tiles (hiển thị mỗi 1s từ logger)
        self.tile_adxl1 = self._tile_unified("ADXL345 1", "Z", "#c77dff")
        self.tile_adxl2 = self._tile_unified("ADXL345 2", "Z", "#ff4d6d")
        self.tile_adxl3 = self._tile_unified("ADXL345 3", "Z", "#00d4ff")

        tiles_layout.addWidget(self.tile_temp)
        tiles_layout.addWidget(self.tile_hum)
        tiles_layout.addWidget(self.tile_wdir)
        tiles_layout.addWidget(self.tile_wspd)
        tiles_layout.addWidget(self.tile_adxl1)
        tiles_layout.addWidget(self.tile_adxl2)
        tiles_layout.addWidget(self.tile_adxl3)
        tiles_layout.addStretch(1)
        main.addLayout(tiles_layout)

        # === Table ===
        self.table = QTableWidget(0, len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        header = self.table.horizontalHeader()
        for i in range(len(TABLE_HEADERS)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f0f0f; alternate-background-color: #1a1a1a;
                gridline-color: #2e2e2e; color: #ffffff; }
            QHeaderView::section { background-color: #1f1f1f; color: #ffffff; font-weight: 700; font-size: 14px; }
        """)
        main.addWidget(self.table, stretch=5)

        # === Plots ===
        plots_rt = QHBoxLayout()
        self.plot_temp = SimplePlot(ylabel="°C", title="Temperature (°C)")
        self.plot_hum = SimplePlot(ylabel="%", title="Humidity (%)")
        self.plot_wspd = SimplePlot(ylabel="m/s", title="Wind Speed (m/s)")
        plots_rt.addWidget(self.plot_temp, 1)
        plots_rt.addWidget(self.plot_hum, 1)
        plots_rt.addWidget(self.plot_wspd, 1)
        main.addLayout(plots_rt, stretch=3)

        # === Timers ===
        self.timer = QTimer(); self.timer.timeout.connect(self.read_all)
        self.csv_path = None
        self.apply_dark_style()

    # === Tile unified ===
    def _tile_unified(self, title, unit, color, with_subline=False):
        f = QFrame()
        f.setFrameShape(QFrame.StyledPanel)
        f.setMinimumWidth(200); f.setMinimumHeight(140)
        v = QVBoxLayout(f); v.setContentsMargins(16, 14, 16, 14); v.setSpacing(6)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color:#ffffff; font-weight:600; font-size:13px;")
        v.addWidget(lbl_title)

        lbl_value = QLabel("-")
        lbl_value.setObjectName(f"tile_value_{title.replace(' ', '_')}")
        lbl_value.setStyleSheet(f"color:{color}; font-size:36px; font-weight:800;")
        v.addWidget(lbl_value)

        if with_subline:
            lbl_sub = QLabel("")
            lbl_sub.setObjectName(f"tile_sub_{title.replace(' ', '_')}")
            lbl_sub.setStyleSheet("color:#bbbbbb; font-size:14px;")
            v.addWidget(lbl_sub)
        else:
            v.addWidget(QLabel(""))

        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color:#ffffff; font-size:13px;")
        v.addWidget(lbl_unit)

        f.setStyleSheet("QFrame {background:#2a2a2a; border-radius:12px;}")
        return f

    def apply_dark_style(self):
        self.setStyleSheet("""
        QWidget { background:#0b0b0b; color:#ddd; font-family:Arial; }
        QPushButton { background:#1f6feb; color:#fff; padding:6px 10px; border-radius:6px; }
        QPushButton:hover { background:#2a8df0; }
        """)

    # === MODBUS functions ===
    def start_reading(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # ---- Modbus CSV (giữ nguyên logic cũ) ----
        self.csv_path = CSV_AUTO_DIR / f"rs485_log_{now}.csv"
        pd.DataFrame(columns=TABLE_HEADERS).to_csv(self.csv_path, index=False)

        # ---- ADXL CSV riêng ----
        self.adxl_csv_path = CSV_AUTO_DIR / f"adxl345_log_{now}.csv"
        # tạo file header ngay để dễ thấy file đã được tạo
        try:
            with open(self.adxl_csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(ADXL_HEADERS)
        except Exception:
            # nếu không tạo được thì vẫn cho Modbus chạy
            self.adxl_csv_path = None

        # ===== ADD: start realtime sender =====
        if self.rt_sender is None:
            self.rt_sender = RealtimeSender(
                SERVER_URL, API_KEY, DEVICE_ID,
                timeout=2.0,
                adxl_batch_size=ADXL_BATCH_SIZE,
                adxl_flush_interval_s=ADXL_FLUSH_INTERVAL_S
            )
            self.rt_sender.start()

        # start ADXL thread
        if self.adxl_csv_path is not None:
            self.adxl_logger = ADXLLogger(self.adxl_csv_path, realtime_sender=self.rt_sender)
            self.adxl_logger.start()

        # start Modbus timer
        self.timer.start(READ_INTERVAL_MS)
        self.btnStart.setEnabled(False); self.btnStop.setEnabled(True)

    def stop_reading(self):
        # stop Modbus
        self.timer.stop()
        self.btnStart.setEnabled(True); self.btnStop.setEnabled(False)

        # stop ADXL
        if self.adxl_logger is not None:
            try:
                self.adxl_logger.stop()
            except Exception:
                pass
            self.adxl_logger = None

        # ===== ADD: stop realtime sender =====
        if self.rt_sender is not None:
            try:
                self.rt_sender.stop()
            except Exception:
                pass
            self.rt_sender = None

    def export_excel_rs485_dialog(self):
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Excel",
            f"sensor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not fname:
            return
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        df = pd.DataFrame(rows, columns=TABLE_HEADERS)
        df.to_excel(fname, index=False)
        QMessageBox.information(self, "Export", f"Exported to {fname}")


    def export_excel_adxl_dialog(self):
        if not self.adxl_csv_path or not Path(self.adxl_csv_path).exists():
            QMessageBox.warning(self, "Export", "Chưa có file adxl345_log để export (hãy bấm Start trước).")
            return
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Excel",
            f"adxl345_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not fname:
            return
        try:
            df = pd.read_csv(self.adxl_csv_path, on_bad_lines="skip")
            df.to_excel(fname, index=False)
            QMessageBox.information(self, "Export", f"Exported to {fname}")
        except Exception as ex:
            QMessageBox.warning(self, "Export", f"Không export được: {ex}")
    def read_all(self):
        t = datetime.now()
        try:
            self.inst_temp.address = ID_TEMP_HUM
            raw_temp = self.inst_temp.read_register(0, functioncode=3)
            time.sleep(0.05)
            raw_hum = self.inst_temp.read_register(1, functioncode=3)
            time.sleep(0.05)

            self.inst_spd.address = ID_WIND_SPD
            raw_wspd = self.inst_spd.read_register(0, functioncode=3)
            time.sleep(0.05)

            self.inst_dir.address = ID_WIND_DIR
            raw_wdir = self.inst_dir.read_register(0, functioncode=3)
            time.sleep(0.05)
        except Exception:
            raw_temp = raw_hum = raw_wdir = raw_wspd = None

        temp = (raw_temp / 10.0) if raw_temp is not None else None
        hum = (raw_hum / 10.0) if raw_hum is not None else None
        wspd = (raw_wspd / 10.0) if raw_wspd is not None else None

        wdir_deg = None if raw_wdir is None else float(raw_wdir) % 360.0
        wdir_txt = "-" if wdir_deg is None else deg_to_cardinal(wdir_deg)

        self.findChild(QLabel, "tile_value_Temperature").setText("" if temp is None else f"{temp:.1f}")
        self.findChild(QLabel, "tile_value_Humidity").setText("" if hum is None else f"{hum:.1f}")
        self.findChild(QLabel, "tile_value_Wind_Speed").setText("" if wspd is None else f"{wspd:.1f}")
        self.findChild(QLabel, "tile_value_Wind_Direction").setText(wdir_txt)

        sub = self.findChild(QLabel, "tile_sub_Wind_Direction")
        if sub is not None:
            sub.setText("" if wdir_deg is None else f"{int(wdir_deg)}°")

        # ADXL tiles update (mỗi 1s)
        latest = None
        if self.adxl_logger is not None:
            try:
                latest = self.adxl_logger.get_latest()
            except Exception:
                latest = None

        lbl1 = self.findChild(QLabel, "tile_value_ADXL345_1")
        lbl2 = self.findChild(QLabel, "tile_value_ADXL345_2")
        lbl3 = self.findChild(QLabel, "tile_value_ADXL345_3")
        if latest is None:
            if lbl1: lbl1.setText("-")
            if lbl2: lbl2.setText("-")
            if lbl3: lbl3.setText("-")
        else:
            z1, z2, z3 = latest
            if lbl1: lbl1.setText(f"{z1}")
            if lbl2: lbl2.setText(f"{z2}")
            if lbl3: lbl3.setText(f"{z3}")

        # table update
        if self.table.rowCount() >= 600:
            self.table.removeRow(0)

        r = self.table.rowCount()
        self.table.insertRow(r)

        time_str = t.strftime("%Y-%m-%d %H:%M:%S")
        items = [
            QTableWidgetItem(time_str),
            QTableWidgetItem("" if temp is None else f"{temp:.1f}"),
            QTableWidgetItem("" if hum is None else f"{hum:.1f}"),
            QTableWidgetItem("" if wdir_deg is None else f"{int(wdir_deg)}"),
            QTableWidgetItem("" if wspd is None else f"{wspd:.1f}")
        ]
        colors = ["#FFFFFF", "#00cc66", "#4da6ff", "#ff9a33", "#ffcc00"]

        for i, it in enumerate(items):
            it.setTextAlignment(Qt.AlignCenter)
            it.setForeground(QColor(colors[i]))
            f = it.font(); f.setBold(True); it.setFont(f)
            it.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(r, i, it)

        self.table.scrollToBottom()

        # CSV append
        if self.csv_path:
            pd.DataFrame([[
                time_str,
                ("" if temp is None else f"{temp:.1f}"),
                ("" if hum is None else f"{hum:.1f}"),
                ("" if wdir_deg is None else f"{int(wdir_deg)}"),
                ("" if wspd is None else f"{wspd:.1f}")
            ]], columns=TABLE_HEADERS).to_csv(
                self.csv_path, mode='a', header=False, index=False
            )

        # ===== ADD: realtime push RS485 (1s) =====
        if self.rt_sender is not None:
            try:
                self.rt_sender.push_rs485({
                    "time_local": time_str,
                    "temp_c": temp,
                    "hum_pct": hum,
                    "wind_dir_deg": wdir_deg,
                    "wind_dir_txt": wdir_txt,
                    "wind_spd_ms": wspd,
                })
            except Exception:
                pass

        # series buffer
        self.data_times.append(t)
        self.data_temp.append(temp)
        self.data_hum.append(hum)
        self.data_wdir_deg.append(wdir_deg)
        self.data_wspd.append(wspd)

        if len(self.data_times) > MAX_SAMPLES:
            self.data_times = self.data_times[-MAX_SAMPLES:]
            self.data_temp = self.data_temp[-MAX_SAMPLES:]
            self.data_hum = self.data_hum[-MAX_SAMPLES:]
            self.data_wdir_deg = self.data_wdir_deg[-MAX_SAMPLES:]
            self.data_wspd = self.data_wspd[-MAX_SAMPLES:]

        self.redraw_plots()

    def redraw_plots(self):
        def filtered(t, v):
            t2, v2 = [], []
            for tt, vv in zip(t, v):
                if vv is None:
                    continue
                t2.append(tt); v2.append(vv)
            return t2, v2

        t1, v1 = filtered(self.data_times, self.data_temp)
        t2, v2 = filtered(self.data_times, self.data_hum)
        t4, v4 = filtered(self.data_times, self.data_wspd)

        self.plot_temp.plot_series(t1, v1, "Temperature (°C)", "#00cc66", y_fixed_range=(10, 50))
        self.plot_hum.plot_series(t2, v2, "Humidity (%)", "#4da6ff", y_fixed_range=(0, 100))
        self.plot_wspd.plot_series(t4, v4, "Wind Speed (m/s)", "#ffcc00")

    def closeEvent(self, e):
        # đảm bảo dừng ADXL khi tắt app
        if self.adxl_logger is not None:
            try:
                self.adxl_logger.stop()
            except Exception:
                pass
            self.adxl_logger = None

        # ===== ADD: stop sender on close =====
        if self.rt_sender is not None:
            try:
                self.rt_sender.stop()
            except Exception:
                pass
            self.rt_sender = None

        e.accept()
