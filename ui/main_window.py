"""
Main window for MacSystemMonitorAI — PyQt6-based system monitoring dashboard.

Displays CPU, memory, disk usage, and network speeds in a clean layout
with Start / Stop buttons to control periodic monitoring.
"""

from __future__ import annotations

import time

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from charts.chart_widget import ChartWidget
from database.database import init_database, save_stats


def _format_bytes_per_sec(bytes_per_sec: float) -> str:
    """Convert a bytes-per-second value to a human-readable string."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.1f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    elif bytes_per_sec < 1024 * 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"


def _format_bytes(num_bytes: int) -> str:
    """Convert a byte count to a human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class _MetricCard(QFrame):
    """A single metric card displaying a label, a large value, and a subtitle."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._title_label.font()
        font.setPointSize(12)
        self._title_label.setFont(font)
        self._title_label.setStyleSheet("color: #888;")

        self._value_label = QLabel("--")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_font = QFont()
        value_font.setPointSize(32)
        value_font.setBold(True)
        self._value_label.setFont(value_font)

        self._sub_label = QLabel("")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setStyleSheet("color: #888;")

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._sub_label)

    def set_value(self, value_text: str, sub_text: str = "") -> None:
        """Update the displayed value and optional subtitle."""
        self._value_label.setText(value_text)
        if sub_text:
            self._sub_label.setText(sub_text)


class MainWindow(QMainWindow):
    """Main application window for the system monitor."""

    _WINDOW_TITLE = "MacSystemMonitorAI"
    _WINDOW_SIZE = (900, 720)
    _UPDATE_INTERVAL_MS = 1000  # 1 second refresh

    def __init__(self) -> None:
        super().__init__()

        # ------------------------------------------------------------------
        # Network-speed tracking state
        # ------------------------------------------------------------------
        self._prev_net_bytes_sent: int = 0
        self._prev_net_bytes_recv: int = 0
        self._prev_net_time: float = 0.0
        self._net_initialised: bool = False

        # ------------------------------------------------------------------
        # Timer (UI refresh, 1 second)
        # ------------------------------------------------------------------
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)

        # ------------------------------------------------------------------
        # Timer (DB persistence, 10 seconds)
        # ------------------------------------------------------------------
        init_database()

        self._db_timer = QTimer(self)
        self._db_timer.setInterval(10_000)  # 10 seconds
        self._db_timer.timeout.connect(self._save_to_db)

        # Latest metric values (refreshed every 1 s, persisted every 10 s)
        self._latest_cpu: float = 0.0
        self._latest_mem: float = 0.0
        self._latest_disk: float = 0.0
        self._latest_upload: float = 0.0
        self._latest_download: float = 0.0

        # ------------------------------------------------------------------
        # History chart
        # ------------------------------------------------------------------
        self._chart = ChartWidget(duration_minutes=10, parent=self)

        # ------------------------------------------------------------------
        # Build UI
        # ------------------------------------------------------------------
        self._setup_ui()

        # Seed the CPU-percent machinery so the first timer tick returns a
        # meaningful value instead of 0.0.
        psutil.cpu_percent(interval=None)

        # Auto-start monitoring on launch
        self._start_monitoring()

        # Initial chart draw (will show "等待数据…" until DB has rows)
        self._chart.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Create and arrange all widgets."""
        self.setWindowTitle(self._WINDOW_TITLE)
        self.resize(*self._WINDOW_SIZE)

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(18)

        # --- Title ---
        title = QLabel(self._WINDOW_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        # --- Metric cards ---
        grid = QGridLayout()
        grid.setSpacing(12)

        self._cpu_card = _MetricCard("CPU 占用率")
        self._mem_card = _MetricCard("内存 占用率")
        self._disk_card = _MetricCard("磁盘 占用率")
        self._up_card = _MetricCard("上传速度")
        self._down_card = _MetricCard("下载速度")

        # Row 0: CPU, Memory, Disk
        grid.addWidget(self._cpu_card, 0, 0)
        grid.addWidget(self._mem_card, 0, 1)
        grid.addWidget(self._disk_card, 0, 2)

        # Row 1: Upload, Download + spacer
        grid.addWidget(self._up_card, 1, 0)
        grid.addWidget(self._down_card, 1, 1)
        # Leave column 2 empty to balance the row visually
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        root.addLayout(grid, stretch=1)

        # --- History chart ---
        root.addWidget(self._chart, stretch=2)

        # --- Bottom buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self._start_btn = QPushButton("开始监控")
        self._start_btn.setMinimumHeight(40)
        self._start_btn.clicked.connect(self._start_monitoring)

        self._stop_btn = QPushButton("停止监控")
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_monitoring)

        btn_layout.addStretch()
        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)
        btn_layout.addStretch()

        root.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Monitoring control
    # ------------------------------------------------------------------

    def _start_monitoring(self) -> None:
        """Begin periodic metric collection."""
        self._reset_network_state()
        self._timer.start(self._UPDATE_INTERVAL_MS)
        self._db_timer.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop_monitoring(self) -> None:
        """Stop periodic metric collection."""
        self._timer.stop()
        self._db_timer.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _reset_network_state(self) -> None:
        """Reset the network-speed tracking so the first reading is
        discarded and subsequent deltas are accurate."""
        self._prev_net_bytes_sent = 0
        self._prev_net_bytes_recv = 0
        self._prev_net_time = 0.0
        self._net_initialised = False

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _update_metrics(self) -> None:
        """Called by the timer on each tick. Reads system data and
        updates the metric cards."""
        now = time.time()

        # -- CPU (non-blocking: interval=None uses the delta since the
        #    last call to cpu_percent) --
        cpu = psutil.cpu_percent(interval=None)
        self._cpu_card.set_value(f"{cpu:.1f}%")
        self._latest_cpu = cpu

        # -- Memory --
        mem = psutil.virtual_memory()
        used_str = _format_bytes(mem.used)
        total_str = _format_bytes(mem.total)
        self._mem_card.set_value(f"{mem.percent:.1f}%", f"{used_str} / {total_str}")
        self._latest_mem = mem.percent

        # -- Disk --
        disk_total = 0
        disk_used = 0
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_total += usage.total
                disk_used += usage.used
            except PermissionError:
                continue
        disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0.0
        used_disk_str = _format_bytes(disk_used)
        total_disk_str = _format_bytes(disk_total)
        self._disk_card.set_value(
            f"{disk_percent:.1f}%", f"{used_disk_str} / {total_disk_str}"
        )
        self._latest_disk = disk_percent

        # -- Network speed (bytes/sec, computed from deltas) --
        upload_speed = 0.0
        download_speed = 0.0
        net = psutil.net_io_counters()
        if self._net_initialised and self._prev_net_time > 0:
            elapsed = now - self._prev_net_time
            if elapsed > 0:
                upload_speed = (net.bytes_sent - self._prev_net_bytes_sent) / elapsed
                download_speed = (
                    net.bytes_recv - self._prev_net_bytes_recv
                ) / elapsed
                self._up_card.set_value(_format_bytes_per_sec(upload_speed))
                self._down_card.set_value(_format_bytes_per_sec(download_speed))
        else:
            self._net_initialised = True

        self._latest_upload = upload_speed
        self._latest_download = download_speed

        self._prev_net_bytes_sent = net.bytes_sent
        self._prev_net_bytes_recv = net.bytes_recv
        self._prev_net_time = now

    def _save_to_db(self) -> None:
        """Persist the latest metric values to the SQLite database."""
        save_stats(
            cpu_percent=self._latest_cpu,
            memory_percent=self._latest_mem,
            disk_percent=self._latest_disk,
            upload_speed=self._latest_upload,
            download_speed=self._latest_download,
        )
        self._chart.refresh()
