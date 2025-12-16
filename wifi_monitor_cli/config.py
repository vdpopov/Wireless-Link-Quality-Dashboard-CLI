"""Configuration and shared state for wifi-monitor-cli."""

from pathlib import Path

import numpy as np

# Time window presets (label -> seconds)
TIME_WINDOWS = {
    "10m": 600,
    "30m": 1800,
    "60m": 3600,
    "4h": 14400,
    "1D": 86400,
    "7D": 604800,
}

PING_COLORS = ["red", "yellow", "magenta", "cyan", "green", "blue"]

# Defaults
DEFAULT_WINDOW = 600
DEFAULT_REFRESH_INTERVAL = 1.0  # seconds

# Shared state (mutated by app)
current_window = DEFAULT_WINDOW
paused = False

signal_data = np.array([])
rx_rate_data = np.array([])
tx_rate_data = np.array([])
bandwidth_data = np.array([])
time_data = np.array([])

signal_failed = np.array([], dtype=bool)
rates_failed = np.array([], dtype=bool)
bandwidth_failed = np.array([], dtype=bool)

INTERFACE = None
REFRESH_INTERVAL = DEFAULT_REFRESH_INTERVAL

ping_hosts = []

# Heatmap settings
HEATMAP_DAYS = 7
SCAN_STORAGE_PATH = Path.home() / ".config" / "wifi-monitor" / "scans"

# Data buffer settings
MAX_DATA_POINTS = 86400  # 1 day at 1 sample/sec
