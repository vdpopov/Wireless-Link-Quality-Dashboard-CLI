"""Live monitoring view for the TUI."""

import time
import numpy as np

from rich.console import Group
from rich.align import Align

from .. import config
from ..core import net, ping
from .components import (
    create_header,
    create_signal_panel,
    create_ping_panel,
    create_rates_graph_panel,
    create_status_line,
    create_help_bar,
)


class LiveView:
    """Live monitoring view with signal, ping, and rate displays."""

    def __init__(self):
        self.last_signal = None
        self.last_rx_rate = None
        self.last_tx_rate = None
        self.last_bandwidth = None
        self.paused_at = None  # Timestamp when pause started

    def collect_data(self):
        """Collect current WiFi metrics and ping data."""
        if config.paused:
            return

        current_time = time.time()

        # Get WiFi link info
        signal, rx_rate, tx_rate, bandwidth = net.get_link_info()

        # Store latest values
        self.last_signal = signal
        self.last_rx_rate = rx_rate
        self.last_tx_rate = tx_rate
        self.last_bandwidth = bandwidth

        # Append to data arrays
        config.time_data = np.append(config.time_data, current_time)
        config.signal_data = np.append(
            config.signal_data, signal if signal is not None else np.nan
        )
        config.rx_rate_data = np.append(
            config.rx_rate_data, rx_rate if rx_rate is not None else np.nan
        )
        config.tx_rate_data = np.append(
            config.tx_rate_data, tx_rate if tx_rate is not None else np.nan
        )
        config.bandwidth_data = np.append(
            config.bandwidth_data, bandwidth if bandwidth is not None else np.nan
        )

        # Track failures
        config.signal_failed = np.append(config.signal_failed, signal is None)
        config.rates_failed = np.append(config.rates_failed, rx_rate is None)
        config.bandwidth_failed = np.append(config.bandwidth_failed, bandwidth is None)

        # Collect ping data (grab current values from background threads)
        for host_info in config.ping_hosts:
            with ping.ping_lock:
                latest = host_info["latest"]
            host_info["data"] = np.append(
                host_info["data"], latest if latest is not None else np.nan
            )
            host_info["failed"] = np.append(host_info["failed"], latest is None)

        # Trim data if too long
        max_points = config.MAX_DATA_POINTS
        if len(config.time_data) > max_points:
            trim = len(config.time_data) - max_points
            config.time_data = config.time_data[trim:]
            config.signal_data = config.signal_data[trim:]
            config.rx_rate_data = config.rx_rate_data[trim:]
            config.tx_rate_data = config.tx_rate_data[trim:]
            config.bandwidth_data = config.bandwidth_data[trim:]
            config.signal_failed = config.signal_failed[trim:]
            config.rates_failed = config.rates_failed[trim:]
            config.bandwidth_failed = config.bandwidth_failed[trim:]

            for host_info in config.ping_hosts:
                host_info["data"] = host_info["data"][trim:]
                host_info["failed"] = host_info["failed"][trim:]

    def get_windowed_data(self, now):
        """Get data for the current time window, with timestamps."""
        if len(config.time_data) == 0:
            return np.array([]), np.array([]), np.array([]), np.array([]), []

        window_seconds = config.current_window

        # Snapshot the arrays to avoid race conditions during rendering
        time_arr = config.time_data
        signal_arr = config.signal_data
        rx_arr = config.rx_rate_data
        tx_arr = config.tx_rate_data

        if window_seconds is None:
            # Show all data
            mask = np.ones(len(time_arr), dtype=bool)
        else:
            cutoff = now - window_seconds
            mask = time_arr >= cutoff

        mask_len = len(mask)
        time_data = time_arr[mask]
        signal_data = signal_arr[mask] if len(signal_arr) == mask_len else np.array([])
        rx_data = rx_arr[mask] if len(rx_arr) == mask_len else np.array([])
        tx_data = tx_arr[mask] if len(tx_arr) == mask_len else np.array([])

        # Get ping data for each host (ensure same length as time_data)
        hosts_data = []
        for host_info in config.ping_hosts:
            ping_data = host_info["data"]
            # Ensure ping data array matches mask length before masking
            if len(ping_data) == mask_len:
                host_data = ping_data[mask]
            else:
                host_data = np.array([])
            hosts_data.append({
                "label": host_info.get("label", host_info.get("host")),
                "data": host_data,
                "latest": host_info.get("latest"),
            })

        return signal_data, time_data, rx_data, tx_data, hosts_data

    def render(self, console_width=80, console_height=24):
        """Render the live view."""
        # Capture current time ONCE for entire render cycle
        # When paused, use the paused_at time to freeze the chart
        if config.paused and self.paused_at:
            now = self.paused_at
        else:
            now = time.time()

        # Get current connection info
        band = net.get_current_band()
        channel = net.get_current_channel()
        ssid = net.get_ssid()

        # Get windowed data using the same timestamp
        signal_history, time_history, rx_history, tx_history, hosts_data = self.get_windowed_data(now)

        # Calculate panel width and consistent layout for all charts
        panel_width = console_width - 4

        # Fixed margins for visual alignment across all charts
        label_width = 8    # Space for labels like "Signal", "gateway", "RX/TX"
        scale_width = 12   # Space for scale values like " 600 Mbps"

        # Calculate bucket count: panel_width - label - scale - borders (▕▏)
        bucket_count = panel_width - label_width - scale_width - 2

        # Calculate dynamic chart height based on terminal height
        # Reserve: header(3) + status(1) + help(1) + panel borders(6) + ping spacing
        num_ping_hosts = len(hosts_data) if hosts_data else 1
        # Fixed reserved lines: header(3) + status line(1) + help bar(1) + 3 panel borders (2 each = 6)
        # Plus spacing between ping hosts and legend line for rates
        reserved_lines = 3 + 1 + 1 + 6 + (num_ping_hosts - 1) + 1
        available_height = console_height - reserved_lines

        # Distribute height among 3 charts (signal, ping per host, rates)
        num_charts = 2 + num_ping_hosts  # signal + rates + ping hosts
        # Minimum height of 1 row per chart, ensure we always have room for help bar
        chart_height = max(1, available_height // num_charts)

        # Build components (all using same 'now', bucket_count, and layout)
        header = create_header(config.INTERFACE, band, channel, ssid)
        signal_panel = create_signal_panel(
            self.last_signal, signal_history, time_history, width=panel_width,
            window_seconds=config.current_window, now=now, bucket_count=bucket_count,
            label_width=label_width, scale_width=scale_width, chart_height=chart_height
        )
        ping_panel = create_ping_panel(
            hosts_data, time_history, width=panel_width,
            window_seconds=config.current_window, now=now, bucket_count=bucket_count,
            label_width=label_width, scale_width=scale_width, chart_height=chart_height
        )
        rates_panel = create_rates_graph_panel(
            rx_history, tx_history, time_history, width=panel_width,
            window_seconds=config.current_window, now=now, bucket_count=bucket_count,
            label_width=label_width, scale_width=scale_width, chart_height=chart_height
        )
        status_line = create_status_line(config.current_window, config.paused)
        help_bar = create_help_bar("live")

        # Compose the view
        return Group(
            header,
            signal_panel,
            ping_panel,
            rates_panel,
            status_line,
            help_bar,
        )

    def handle_key(self, key):
        """
        Handle keypress for live view.

        Returns:
            str or None: 'quit', 'heatmap', or None to stay in view
        """
        if key == 'q':
            return 'quit'
        elif key == 'h':
            return 'heatmap'
        elif key == 'p':
            config.paused = not config.paused
            if config.paused:
                self.paused_at = time.time()
            else:
                self.paused_at = None
        elif key == '+' or key == '=':
            self._decrease_window()
        elif key == '-':
            self._increase_window()
        elif key == 'a':
            return 'add_host'
        elif key == 'd':
            return 'delete_host'

        return None

    def _increase_window(self):
        """Increase time window to next preset."""
        windows = list(config.TIME_WINDOWS.values())
        current = config.current_window
        for i, w in enumerate(windows):
            if w == current and i < len(windows) - 1:
                config.current_window = windows[i + 1]
                break

    def _decrease_window(self):
        """Decrease time window to previous preset."""
        windows = list(config.TIME_WINDOWS.values())
        current = config.current_window
        for i, w in enumerate(windows):
            if w == current and i > 0:
                config.current_window = windows[i - 1]
                break
