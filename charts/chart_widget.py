"""
ChartWidget — matplotlib-based history trend chart for system metrics.

Displays CPU and memory usage curves over time, reading data from
the SQLite database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import MaxNLocator
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from database.database import get_recent_stats

# ------------------------------------------------------------------
# CJK-capable font (macOS system fonts that cover Chinese)
# ------------------------------------------------------------------
_CJK_FONT_CANDIDATES = [
    "PingFang SC",
    "Heiti SC",
    "STHeiti",
    "Apple LiGothic",
    "Arial Unicode MS",
]


def _find_cjk_font() -> str:
    """Return the first available CJK-capable font on the system."""
    from matplotlib.font_manager import fontManager

    available = {f.name for f in fontManager.ttflist}
    for name in _CJK_FONT_CANDIDATES:
        if name in available:
            return name
    # Fallback — CJK glyphs will show as tofu (□)
    return "DejaVu Sans"


_CJK_FONT_FAMILY = _find_cjk_font()


class ChartWidget(QWidget):
    """A widget that renders CPU and memory history trend lines using matplotlib.

    Data is read from the SQLite database via ``get_recent_stats()``.
    Call ``refresh()`` to re-query and redraw the chart.
    """

    _CPU_COLOR = "#4A90D9"        # blue
    _MEM_COLOR = "#E8913A"        # orange
    _GRID_COLOR = "#444444"
    _BG_COLOR = "#2B2B2B"
    _TEXT_COLOR = "#CCCCCC"

    def __init__(
        self,
        duration_minutes: int = 10,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the chart widget.

        Args:
            duration_minutes: How many minutes of history to display.
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._duration_minutes = duration_minutes

        # ---- CJK font ----
        self._font = FontProperties(family=_CJK_FONT_FAMILY)

        # ---- Figure & canvas ----
        self._figure = Figure(figsize=(8, 3.5), tight_layout=True)
        self._figure.set_facecolor(self._BG_COLOR)

        self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor(self._BG_COLOR)
        self._ax.set_ylim(0, 100)
        self._ax.set_ylabel("%", color=self._TEXT_COLOR, fontproperties=self._font)
        self._ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        self._ax.tick_params(colors=self._TEXT_COLOR, labelsize=8)
        self._ax.grid(True, color=self._GRID_COLOR, linewidth=0.5, alpha=0.7)
        self._ax.spines["bottom"].set_color(self._GRID_COLOR)
        self._ax.spines["top"].set_color(self._GRID_COLOR)
        self._ax.spines["left"].set_color(self._GRID_COLOR)
        self._ax.spines["right"].set_color(self._GRID_COLOR)

        # line objects (created on first refresh)
        self._cpu_line = None
        self._mem_line = None

        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # ---- Layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_duration(self, minutes: int) -> None:
        """Change the history window and refresh immediately."""
        self._duration_minutes = max(1, minutes)
        self.refresh()

    def refresh(self) -> None:
        """Query the database and redraw the chart."""
        rows = self._fetch_data()

        if not rows:
            self._ax.set_title(
                "等待数据…", color=self._TEXT_COLOR, fontsize=11,
                fontproperties=self._font,
            )
            self._canvas.draw()
            return

        timestamps = [datetime.fromtimestamp(r["timestamp"], tz=timezone.utc) for r in rows]
        cpu_vals = [r["cpu_percent"] for r in rows]
        mem_vals = [r["memory_percent"] for r in rows]

        if self._cpu_line is None:
            # First draw — create line artists
            self._cpu_line = self._ax.plot(
                timestamps, cpu_vals,
                color=self._CPU_COLOR, linewidth=1.2, label="CPU",
            )[0]
            self._mem_line = self._ax.plot(
                timestamps, mem_vals,
                color=self._MEM_COLOR, linewidth=1.2, label="Memory",
            )[0]
            self._ax.legend(
                loc="upper right",
                facecolor=self._BG_COLOR,
                edgecolor=self._GRID_COLOR,
                labelcolor=self._TEXT_COLOR,
                fontsize=9,
                prop=self._font,
            )
        else:
            self._cpu_line.set_data(timestamps, cpu_vals)
            self._mem_line.set_data(timestamps, mem_vals)

        # Auto-range X axis
        self._ax.set_xlim(timestamps[0], timestamps[-1])
        self._ax.set_ylim(
            min(min(cpu_vals), min(mem_vals), 0) - 2,
            max(max(cpu_vals), max(mem_vals), 100) + 2,
        )

        self._ax.set_title(
            f"CPU / 内存历史趋势（最近 {self._duration_minutes} 分钟）",
            color=self._TEXT_COLOR,
            fontsize=11,
            fontproperties=self._font,
        )

        self._figure.autofmt_xdate(rotation=30, ha="right")
        self._canvas.draw()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_data(self) -> list[dict]:
        """Read rows from the database for the configured time window.

        We request ``duration_minutes * 60`` rows, which corresponds to
        ~1 row per second (the UI refresh rate). The DB timer writes
        every 10 s, so the actual resolution is coarser — the extra rows
        are harmless and get_recent_stats is cheap.
        """
        limit = self._duration_minutes * 60
        rows = get_recent_stats(limit=limit)
        # get_recent_stats returns newest-first; reverse for chronological plot
        rows.reverse()
        return rows
