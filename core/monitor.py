"""
System monitor module - Collects system metrics via psutil.

Provides:
- get_cpu_usage()
- get_memory_usage()
- get_disk_usage()
- get_network_speed()
"""

import psutil


def get_cpu_usage() -> dict:
    """Get CPU usage metrics.

    Returns:
        dict with keys:
            percent (float): Overall CPU usage percentage (0-100).
            per_cpu (list[float]): Per-core usage percentages.
            count (int): Number of logical CPU cores.
    """
    return {
        "percent": psutil.cpu_percent(interval=1),
        "per_cpu": psutil.cpu_percent(interval=0, percpu=True),
        "count": psutil.cpu_count(logical=True),
    }


def get_memory_usage() -> dict:
    """Get virtual memory and swap usage metrics.

    Returns:
        dict with keys:
            total (int): Total physical memory in bytes.
            available (int): Available memory in bytes.
            used (int): Used memory in bytes.
            percent (float): Memory usage percentage (0-100).
            swap_total (int): Total swap memory in bytes.
            swap_used (int): Used swap memory in bytes.
            swap_percent (float): Swap usage percentage (0-100).
    """
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "used": mem.used,
        "percent": mem.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
    }


def get_disk_usage() -> dict:
    """Get disk usage metrics for all mounted partitions.

    Returns:
        dict with keys:
            total (int): Total disk space in bytes.
            used (int): Used disk space in bytes.
            free (int): Free disk space in bytes.
            percent (float): Disk usage percentage (0-100).
            partitions (list[dict]): Per-partition details:
                - mountpoint (str)
                - device (str)
                - fstype (str)
                - total (int)
                - used (int)
                - free (int)
                - percent (float)
    """
    partitions = []

    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "mountpoint": part.mountpoint,
                "device": part.device,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except PermissionError:
            continue

    # On macOS with APFS, multiple volumes share the same container.
    # Summing all partitions inflates total/used by 2-5×. Use `/`
    # only for the summary — it correctly reports the APFS container
    # totals on macOS.
    try:
        root_usage = psutil.disk_usage("/")
        total = root_usage.total
        used = root_usage.used
        free = root_usage.free
        percent = root_usage.percent
    except PermissionError:
        total = used = free = 0
        percent = 0.0

    return {
        "total": total,
        "used": used,
        "free": free,
        "percent": round(percent, 1),
        "partitions": partitions,
    }


def get_network_speed() -> dict:
    """Get current network I/O counters.

    Returns:
        dict with keys:
            bytes_sent (int): Total bytes sent.
            bytes_recv (int): Total bytes received.
            packets_sent (int): Total packets sent.
            packets_recv (int): Total packets received.
            per_nic (list[dict]): Per-NIC details:
                - name (str)
                - bytes_sent (int)
                - bytes_recv (int)
                - packets_sent (int)
                - packets_recv (int)
    """
    counters = psutil.net_io_counters(pernic=True)
    total_sent = 0
    total_recv = 0
    total_psent = 0
    total_precv = 0
    per_nic = []

    net_io_counters = psutil.net_io_counters()
    total_sent = net_io_counters.bytes_sent
    total_recv = net_io_counters.bytes_recv
    total_psent = net_io_counters.packets_sent
    total_precv = net_io_counters.packets_recv

    for name, stats in counters.items():
        per_nic.append({
            "name": name,
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv,
        })

    return {
        "bytes_sent": total_sent,
        "bytes_recv": total_recv,
        "packets_sent": total_psent,
        "packets_recv": total_precv,
        "per_nic": per_nic,
    }
