"""Background ping thread management."""

import re
import threading
import time
import subprocess

import numpy as np

from .. import config


ping_lock = threading.Lock()
ping_threads_running = True

gateway_host_info = None
gateway_removed_by_user = False


def ping_worker(host_info):
    """Background worker that continuously pings a host."""
    while ping_threads_running:
        if not host_info.get("enabled", True):
            time.sleep(0.5)
            continue
        try:
            result = subprocess.check_output(
                ["ping", "-c", "1", "-W", "1", host_info["host"]],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            match = re.search(r"time=([\d.]+)", result)
            with ping_lock:
                host_info["latest"] = float(match.group(1)) if match else None
        except Exception:
            with ping_lock:
                host_info["latest"] = None
        time.sleep(0.5)


def add_ping_host(host, label=None):
    """
    Add a new host to ping.

    Args:
        host: IP address or hostname to ping
        label: Display label (defaults to host)

    Returns:
        dict: The host info dictionary
    """
    current_len = len(config.time_data)
    host_info = {
        "host": host,
        "label": label or host,
        "enabled": True,
        "data": np.full(current_len, np.nan),
        "failed": np.ones(current_len, dtype=bool),
        "latest": None,
        "thread": None,
    }
    thread = threading.Thread(target=ping_worker, args=(host_info,), daemon=True)
    host_info["thread"] = thread
    thread.start()
    config.ping_hosts.append(host_info)
    return host_info


def remove_ping_host(index):
    """Remove a ping host by index."""
    if 0 <= index < len(config.ping_hosts):
        config.ping_hosts[index]["enabled"] = False
        config.ping_hosts.pop(index)


def stop_all_ping_threads():
    """Signal all ping threads to stop."""
    global ping_threads_running
    ping_threads_running = False
