"""Reusable UI components built with rich."""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.align import Align

from .. import config
from .charts import multi_sparkline, multi_sparkline_overlay, progress_bar, signal_color, ping_color, bucket_by_time


def create_header(interface, band, channel, ssid):
    """Create the top header showing connection info."""
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_column(justify="left")

    table.add_row(
        Text(f"Interface: ", style="dim") + Text(interface or "N/A", style="bold cyan"),
        Text(f"Band: ", style="dim") + Text(f"{band or '?'}GHz", style="bold yellow"),
        Text(f"Ch: ", style="dim") + Text(str(channel or "?"), style="bold green"),
        Text(f"SSID: ", style="dim") + Text(ssid or "N/A", style="bold white"),
    )

    return Panel(table, title="WiFi Monitor", border_style="blue")


def create_signal_panel(signal_dbm, signal_history, timestamps, width=50, window_seconds=600, now=None, bucket_count=None, label_width=8, scale_width=10, chart_height=8):
    """Create signal strength panel with colored sparkline."""
    # Fixed range for signal strength (prevents rescaling)
    SIGNAL_MIN = -90  # dBm
    SIGNAL_MAX = -30  # dBm

    label = "Signal"

    # Use provided bucket_count for consistent timing across all charts
    num_buckets = bucket_count if bucket_count else width - label_width - scale_width - 2

    # Bucket data by fixed time slots for stable rendering
    bucketed = bucket_by_time(signal_history, timestamps, window_seconds, num_buckets, now=now)

    # Check if we have any valid data
    valid_data = bucketed[~np.isnan(bucketed)] if len(bucketed) > 0 else np.array([])

    if len(valid_data) > 0:
        rows = multi_sparkline(bucketed, width=num_buckets, height=chart_height,
                               color_func=signal_color, fixed_min=SIGNAL_MIN, fixed_max=SIGNAL_MAX)

        lines = []
        for row_idx, row_data in enumerate(rows):
            line = Text()
            # Label on left (only on top row), right-aligned to label_width
            if row_idx == 0:
                line.append(f"{label:>{label_width}} ", style="bold cyan")
            else:
                line.append(" " * (label_width + 1))

            line.append(f"▕", style="dim")

            for char, color in row_data:
                line.append(char, style=color)

            # Show fixed max/min and unit on right
            if row_idx == 0:
                line.append(f"▏{SIGNAL_MAX:>5} dBm  ", style="dim")
            elif row_idx == chart_height - 1:
                line.append(f"▏{SIGNAL_MIN:>5}      ", style="dim")
            else:
                line.append(f"▏            ", style="dim")
            lines.append(line)

        content = Group(*lines)
    else:
        content = Text("  No history data", style="dim")

    return Panel(content, title="Signal", border_style="cyan")


def create_ping_panel(hosts, timestamps, width=50, window_seconds=600, now=None, bucket_count=None, label_width=8, scale_width=10, chart_height=8):
    """Create ping panel with colored sparklines for each host."""
    # Fixed range for ping (prevents rescaling)
    PING_MIN = 0    # ms
    PING_MAX = 200  # ms

    if not hosts:
        return Panel(Text("No ping hosts", style="dim"), title="Ping", border_style="yellow")

    all_lines = []

    # Use provided bucket_count for consistent timing across all charts
    num_buckets = bucket_count if bucket_count else width - label_width - scale_width - 2

    for host_idx, host in enumerate(hosts):
        label = host.get("label", host.get("host", "?"))[:label_width]
        data = np.asarray(host.get("data", []))

        # Bucket data by fixed time slots for stable rendering
        bucketed = bucket_by_time(data, timestamps, window_seconds, num_buckets, now=now)

        # Check if we have valid data
        valid_data = bucketed[~np.isnan(bucketed)] if len(bucketed) > 0 else np.array([])

        if len(valid_data) > 0:
            rows = multi_sparkline(bucketed, width=num_buckets, height=chart_height,
                                   color_func=ping_color, fixed_min=PING_MIN, fixed_max=PING_MAX)

            for row_idx, row_data in enumerate(rows):
                row_line = Text()

                # Label on left (only on top row), right-aligned to label_width
                if row_idx == 0:
                    row_line.append(f"{label:>{label_width}} ", style="bold yellow")
                else:
                    row_line.append(" " * (label_width + 1))

                row_line.append(f"▕", style="dim")

                for char, color in row_data:
                    row_line.append(char, style=color)

                # Show fixed max/min and unit on right
                if row_idx == 0:
                    row_line.append(f"▏{PING_MAX:>5} ms   ", style="dim")
                elif row_idx == chart_height - 1:
                    row_line.append(f"▏{PING_MIN:>5}      ", style="dim")
                else:
                    row_line.append(f"▏            ", style="dim")
                all_lines.append(row_line)

        # Add spacing between hosts
        if host_idx < len(hosts) - 1:
            all_lines.append(Text(""))

    content = Group(*all_lines)
    return Panel(content, title="Ping", border_style="yellow")


def create_rates_graph_panel(rx_history, tx_history, timestamps, width=50, window_seconds=600, now=None, bucket_count=None, label_width=8, scale_width=10, chart_height=8):
    """Create RX/TX rates panel with overlaid graph."""
    RATE_MIN = 0

    label = "RX/TX"

    # Use provided bucket_count for consistent timing across all charts
    num_buckets = bucket_count if bucket_count else width - label_width - scale_width - 2

    # Bucket data by fixed time slots
    rx_bucketed = bucket_by_time(rx_history, timestamps, window_seconds, num_buckets, now=now)
    tx_bucketed = bucket_by_time(tx_history, timestamps, window_seconds, num_buckets, now=now)

    # Check if we have valid data
    rx_valid = rx_bucketed[~np.isnan(rx_bucketed)] if len(rx_bucketed) > 0 else np.array([])
    tx_valid = tx_bucketed[~np.isnan(tx_bucketed)] if len(tx_bucketed) > 0 else np.array([])

    # Dynamic max based on observed rates, rounded up to nice values
    all_valid = np.concatenate([rx_valid, tx_valid]) if len(rx_valid) > 0 or len(tx_valid) > 0 else np.array([])
    if len(all_valid) > 0:
        max_observed = np.max(all_valid)
        # Round up to next 100, minimum 100
        RATE_MAX = max(100, int(np.ceil(max_observed / 100) * 100))
    else:
        RATE_MAX = 100

    if len(rx_valid) > 0 or len(tx_valid) > 0:
        rows = multi_sparkline_overlay(
            rx_bucketed, tx_bucketed,
            width=num_buckets, height=chart_height,
            color1="green", color2="blue",
            fixed_min=RATE_MIN, fixed_max=RATE_MAX
        )

        lines = []
        for row_idx, row_data in enumerate(rows):
            line = Text()
            # Label on left (only on top row), right-aligned to label_width
            if row_idx == 0:
                line.append(f"{label:>{label_width}} ", style="bold white")
            else:
                line.append(" " * (label_width + 1))

            line.append(f"▕", style="dim")

            for char, color in row_data:
                line.append(char, style=color)

            # Show fixed max/min and unit on right
            if row_idx == 0:
                line.append(f"▏{RATE_MAX:>5} Mbps ", style="dim")
            elif row_idx == chart_height - 1:
                line.append(f"▏{RATE_MIN:>5}      ", style="dim")
            else:
                line.append(f"▏            ", style="dim")
            lines.append(line)

        # Add legend (aligned with chart)
        legend = Text()
        legend.append(" " * (label_width + 2))
        legend.append("▋ RX ", style="green")
        legend.append("▋ TX", style="blue")
        lines.append(legend)

        content = Group(*lines)
    else:
        content = Text("  No rate data", style="dim")

    return Panel(content, title="Data Rates", border_style="green")


def create_rates_panel(rx_rate, tx_rate, bandwidth):
    """Create RX/TX rates panel with progress bars."""
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", no_wrap=True)  # Label
    table.add_column(justify="right", no_wrap=True)  # Value
    table.add_column(no_wrap=True)                   # Bar

    # RX
    if rx_rate is not None:
        rx_bar = progress_bar(rx_rate, 0, 500, width=30)
        table.add_row(
            Text("RX", style="bold green"),
            Text(f"{rx_rate:4.0f} Mbps", style="green"),
            Text(rx_bar, style="green"),
        )
    else:
        table.add_row(
            Text("RX", style="dim"),
            Text("  -- Mbps", style="dim"),
            Text("░" * 30, style="dim"),
        )

    # TX
    if tx_rate is not None:
        tx_bar = progress_bar(tx_rate, 0, 500, width=30)
        table.add_row(
            Text("TX", style="bold blue"),
            Text(f"{tx_rate:4.0f} Mbps", style="blue"),
            Text(tx_bar, style="blue"),
        )
    else:
        table.add_row(
            Text("TX", style="dim"),
            Text("  -- Mbps", style="dim"),
            Text("░" * 30, style="dim"),
        )

    # Bandwidth
    if bandwidth is not None:
        table.add_row(
            Text("BW", style="bold magenta"),
            Text(f"{bandwidth:4.0f} MHz", style="magenta"),
            Text(""),
        )
    else:
        table.add_row(
            Text("BW", style="dim"),
            Text("  -- MHz", style="dim"),
            Text(""),
        )

    return Panel(table, title="Data Rates", border_style="green")


def create_status_line(current_window, paused):
    """Create the status/window selector line."""
    parts = []

    # Time windows
    for label, seconds in config.TIME_WINDOWS.items():
        if seconds == current_window:
            parts.append(Text(f"[{label}]", style="bold cyan"))
        else:
            parts.append(Text(f" {label} ", style="dim"))

    parts.append(Text("    ", style="dim"))

    # Paused indicator
    if paused:
        parts.append(Text(" PAUSED ", style="bold red on white"))

    text = Text()
    for part in parts:
        text.append(part)

    return Align.center(text)


def create_help_bar(view="live"):
    """Create the bottom help bar with available commands."""
    if view == "live":
        keys = [
            ("q", "quit"),
            ("h", "heatmap"),
            ("p", "pause"),
            ("+/-", "window"),
            ("a", "add host"),
            ("d", "del host"),
        ]
    else:  # heatmap
        keys = [
            ("q", "quit"),
            ("l", "live"),
        ]

    text = Text()
    for i, (key, desc) in enumerate(keys):
        if i > 0:
            text.append("  ", style="dim")
        text.append(f"[{key}]", style="bold cyan")
        text.append(f" {desc}", style="dim")

    return Align.center(text)


# Need numpy for ping panel
import numpy as np
