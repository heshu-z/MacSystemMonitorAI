"""
ai_analyzer — Local rule-based system status analyzer.

Reads the last N minutes of monitoring data from SQLite and produces
a structured anomaly report for CPU, memory, disk, and network metrics.

All analysis is performed locally (statistical thresholds, trend detection).
No external API calls are made.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from database.database import get_recent_stats

# ------------------------------------------------------------------
# Thresholds (percentages, 0-100)
# ------------------------------------------------------------------

CPU_WARN_PCT = 70.0       # avg CPU above this → warning
CPU_CRIT_PCT = 85.0       # avg CPU above this → critical
CPU_SPIKE_PCT = 95.0      # any single reading above this → spike alert
CPU_STDEV_FACTOR = 2.0    # multiplier on stdev for fluctuation check

MEM_WARN_PCT = 80.0
MEM_CRIT_PCT = 90.0
MEM_TREND_WINDOW = 10     # number of recent samples for upward-trend check
MEM_TREND_PCT = 3.0       # percentage-point increase over trend window

DISK_WARN_PCT = 85.0
DISK_CRIT_PCT = 95.0

NET_ZERO_THRESHOLD = 100.0     # B/s — below this is considered "idle / possibly down"
NET_HIGH_UPLOAD = 10 * 1024 * 1024   # 10 MB/s
NET_HIGH_DOWNLOAD = 50 * 1024 * 1024 # 50 MB/s


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class MetricStatus:
    """Anomaly assessment for a single metric category."""

    label: str                # human-readable name, e.g. "CPU"
    is_anomalous: bool        # True if any check flagged an anomaly
    severity: str             # "normal" | "warning" | "critical"
    summary: str              # one-line human-readable verdict
    details: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "is_anomalous": self.is_anomalous,
            "severity": self.severity,
            "summary": self.summary,
            "details": self.details,
            "stats": self.stats,
        }


@dataclass
class SystemStatus:
    """Aggregate system status report."""

    ok: bool                  # True if no anomalies found
    summary: str              # overall one-liner
    cpu: MetricStatus
    memory: MetricStatus
    disk: MetricStatus
    network: MetricStatus
    data_points: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disk": self.disk.to_dict(),
            "network": self.network.to_dict(),
            "data_points": self.data_points,
        }


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def analyze(duration_minutes: int = 30, db_path: str | None = None) -> SystemStatus:
    """Run the full system analysis and return a ``SystemStatus``.

    Args:
        duration_minutes: How many minutes of history to analyse.
            Defaults to 30.
        db_path: Optional path to the SQLite database file.
    """
    rows = get_recent_stats(limit=duration_minutes * 60, db_path=db_path)
    if not rows:
        return SystemStatus(
            ok=True,
            summary="暂无足够数据进行分析",
            cpu=MetricStatus("CPU", False, "normal", "无数据"),
            memory=MetricStatus("内存", False, "normal", "无数据"),
            disk=MetricStatus("磁盘", False, "normal", "无数据"),
            network=MetricStatus("网络", False, "normal", "无数据"),
            data_points=0,
        )

    # get_recent_stats returns newest-first; reverse to chronological order
    rows.reverse()

    cpu_vals = [r["cpu_percent"] for r in rows]
    mem_vals = [r["memory_percent"] for r in rows]
    disk_vals = [r["disk_percent"] for r in rows]
    up_vals = [r["upload_speed"] for r in rows]
    down_vals = [r["download_speed"] for r in rows]

    cpu = _analyse_cpu(cpu_vals)
    mem = _analyse_memory(mem_vals)
    disk = _analyse_disk(disk_vals)
    net = _analyse_network(up_vals, down_vals)

    all_ok = not any(s.is_anomalous for s in (cpu, mem, disk, net))
    if all_ok:
        overall = "系统运行正常"
    else:
        anomalies = [s.label for s in (cpu, mem, disk, net) if s.is_anomalous]
        overall = f"检测到异常: {', '.join(anomalies)}"

    return SystemStatus(
        ok=all_ok,
        summary=overall,
        cpu=cpu,
        memory=mem,
        disk=disk,
        network=net,
        data_points=len(rows),
    )


# ------------------------------------------------------------------
# Per-metric analyzers
# ------------------------------------------------------------------

def _compute_stats(values: list[float]) -> dict[str, float]:
    """Compute common statistical measures for a list of values."""
    if not values:
        return {}
    return {
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(statistics.mean(values), 2),
        "stdev": round(statistics.stdev(values), 2) if len(values) >= 2 else 0.0,
    }


def _severity(
    avg: float,
    warn: float,
    crit: float,
    extra_crit: bool = False,
) -> str:
    """Map a metric average onto a severity level."""
    if avg >= crit or extra_crit:
        return "critical"
    if avg >= warn:
        return "warning"
    return "normal"


def _analyse_cpu(values: list[float]) -> MetricStatus:
    stats = _compute_stats(values)
    avg = stats["avg"]
    mx = stats["max"]
    stdev = stats["stdev"]

    details: list[str] = []
    crit_flag = False

    # 1. Average load
    if avg >= CPU_CRIT_PCT:
        details.append(f"CPU 平均使用率 {avg:.1f}% 超过严重阈值 {CPU_CRIT_PCT}%")
        crit_flag = True
    elif avg >= CPU_WARN_PCT:
        details.append(f"CPU 平均使用率 {avg:.1f}% 超过警告阈值 {CPU_WARN_PCT}%")

    # 2. Spike check
    spike_count = sum(1 for v in values if v >= CPU_SPIKE_PCT)
    if spike_count > 0:
        details.append(f"检测到 {spike_count} 次 CPU 峰值 (≥{CPU_SPIKE_PCT}%), 最高 {mx:.1f}%")
        if spike_count >= 3:
            crit_flag = True

    # 3. Volatility
    if stdev > 0 and avg > 20:
        # High volatility while under non-trivial load may indicate issues
        if stdev > avg * 0.5:
            details.append(f"CPU 使用率波动较大 (标准差 {stdev:.1f})")

    is_anom = len(details) > 0
    sev = _severity(avg, CPU_WARN_PCT, CPU_CRIT_PCT, crit_flag)
    if is_anom and sev == "normal":
        sev = "warning"

    return MetricStatus(
        label="CPU",
        is_anomalous=is_anom,
        severity=sev,
        summary=_make_summary("CPU", sev, avg, details),
        details=details,
        stats=stats,
    )


def _analyse_memory(values: list[float]) -> MetricStatus:
    stats = _compute_stats(values)
    avg = stats["avg"]
    mx = stats["max"]

    details: list[str] = []
    crit_flag = False

    # 1. High usage
    if avg >= MEM_CRIT_PCT:
        details.append(f"内存平均使用率 {avg:.1f}% 超过严重阈值 {MEM_CRIT_PCT}%")
        crit_flag = True
    elif avg >= MEM_WARN_PCT:
        details.append(f"内存平均使用率 {avg:.1f}% 超过警告阈值 {MEM_WARN_PCT}%")

    if mx >= MEM_CRIT_PCT + 5:
        details.append(f"内存峰值达到 {mx:.1f}%")
        crit_flag = True

    # 2. Upward trend (potential leak)
    if len(values) >= MEM_TREND_WINDOW:
        recent = values[-MEM_TREND_WINDOW:]
        older = values[-MEM_TREND_WINDOW * 2 : -MEM_TREND_WINDOW]
        if older and len(older) >= MEM_TREND_WINDOW:
            recent_avg = statistics.mean(recent)
            older_avg = statistics.mean(older)
            if recent_avg - older_avg >= MEM_TREND_PCT:
                details.append(
                    f"内存使用呈上升趋势 "
                    f"({older_avg:.1f}% → {recent_avg:.1f}%，"
                    f"增幅 {recent_avg - older_avg:.1f}个百分点）"
                )

    is_anom = len(details) > 0
    sev = _severity(avg, MEM_WARN_PCT, MEM_CRIT_PCT, crit_flag)
    # Trend-only anomalies should still be flagged as warning
    if is_anom and sev == "normal":
        sev = "warning"

    return MetricStatus(
        label="内存",
        is_anomalous=is_anom,
        severity=sev,
        summary=_make_summary("内存", sev, avg, details),
        details=details,
        stats=stats,
    )


def _analyse_disk(values: list[float]) -> MetricStatus:
    stats = _compute_stats(values)
    avg = stats["avg"]
    mx = stats["max"]

    details: list[str] = []
    crit_flag = False

    if avg >= DISK_CRIT_PCT:
        details.append(f"磁盘使用率 {avg:.1f}% 超过严重阈值 {DISK_CRIT_PCT}%，请尽快清理")
        crit_flag = True
    elif avg >= DISK_WARN_PCT:
        details.append(f"磁盘使用率 {avg:.1f}% 超过警告阈值 {DISK_WARN_PCT}%，建议关注")

    if mx >= DISK_CRIT_PCT:
        details.append(f"磁盘使用率峰值达 {mx:.1f}%")

    is_anom = len(details) > 0
    sev = _severity(avg, DISK_WARN_PCT, DISK_CRIT_PCT, crit_flag)
    if is_anom and sev == "normal":
        sev = "warning"

    return MetricStatus(
        label="磁盘",
        is_anomalous=is_anom,
        severity=sev,
        summary=_make_summary("磁盘", sev, avg, details),
        details=details,
        stats=stats,
    )


def _analyse_network(
    up_values: list[float],
    down_values: list[float],
) -> MetricStatus:
    up_stats = _compute_stats(up_values)
    down_stats = _compute_stats(down_values)

    up_avg = up_stats["avg"]
    down_avg = down_stats["avg"]
    up_max = up_stats["max"]
    down_max = down_stats["max"]

    details: list[str] = []
    crit_flag = False

    # 1. Zero / very low throughput (possible disconnect)
    up_zero = sum(1 for v in up_values if v < NET_ZERO_THRESHOLD)
    down_zero = sum(1 for v in down_values if v < NET_ZERO_THRESHOLD)
    zero_ratio = max(up_zero, down_zero) / max(len(up_values), 1)

    if zero_ratio > 0.95:
        details.append("网络近乎无流量，可能已断开连接")
        crit_flag = True
    elif zero_ratio > 0.7:
        details.append("网络流量长时间极低，请检查连接")

    # 2. High throughput
    if up_max > NET_HIGH_UPLOAD:
        details.append(f"上传速度峰值 {_fmt_speed(up_max)}，可能存在大文件上传")
    if down_max > NET_HIGH_DOWNLOAD:
        details.append(f"下载速度峰值 {_fmt_speed(down_max)}，可能存在大文件下载")

    # 3. Sustained high throughput
    if up_avg > NET_HIGH_UPLOAD:
        details.append(f"上传持续高速 {_fmt_speed(up_avg)}")
    if down_avg > NET_HIGH_DOWNLOAD:
        details.append(f"下载持续高速 {_fmt_speed(down_avg)}")

    is_anom = len(details) > 0
    sev = "critical" if crit_flag else ("warning" if is_anom else "normal")

    combined_stats = {
        **{f"up_{k}": v for k, v in up_stats.items()},
        **{f"down_{k}": v for k, v in down_stats.items()},
    }

    return MetricStatus(
        label="网络",
        is_anomalous=is_anom,
        severity=sev,
        summary=_make_summary_net(sev, up_avg, down_avg, details),
        details=details,
        stats=combined_stats,
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_summary(
    name: str,
    sev: str,
    avg: float,
    details: list[str],
) -> str:
    if sev == "normal":
        return f"{name}正常 (平均 {avg:.1f}%)"
    if sev == "critical":
        return f"{name}严重异常 — {details[0]}"
    return f"{name}需注意 — {details[0]}"


def _make_summary_net(
    sev: str,
    up_avg: float,
    down_avg: float,
    details: list[str],
) -> str:
    if sev == "normal":
        return f"网络正常 (↑{_fmt_speed(up_avg)} ↓{_fmt_speed(down_avg)})"
    if sev == "critical":
        return f"网络严重异常 — {details[0]}"
    return f"网络需注意 — {details[0]}"


def _fmt_speed(bps: float) -> str:
    """Format bytes-per-second to human-readable string."""
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    elif bps < 1024 * 1024 * 1024:
        return f"{bps / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bps / (1024 * 1024 * 1024):.2f} GB/s"
