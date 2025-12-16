"""Channel congestion heatmap view for the TUI."""

from datetime import datetime
import numpy as np

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align

from .. import config
from ..core import storage, scanner, net
from .charts import get_congestion_color
from .components import create_help_bar


class HeatmapView:
    """Channel congestion heatmap view."""

    def __init__(self):
        self.days = 7
        self.band = None  # Auto-detect
        self.last_scan_time = None
        self.data = None
        self.dates = None
        self.channels = None
        self.scanning = False

    def load_data(self):
        """Load heatmap data from storage."""
        self.data, self.dates, self.channels, detected_band = storage.get_heatmap_data(
            days=self.days, band=self.band
        )
        if self.band is None:
            self.band = detected_band
        self.last_scan_time = storage.get_last_scan_time()

    def trigger_scan(self):
        """Trigger a new channel scan."""
        self.scanning = True
        scan_result = scanner.scan_channels(band=self.band)
        if scan_result:
            storage.save_scan(scan_result)
            self.load_data()
        self.scanning = False

    def render(self, console_width=80, console_height=24):
        """Render the heatmap view layout."""
        if self.data is None:
            self.load_data()

        # Handle empty data
        if self.dates is None or self.channels is None or self.data is None:
            from rich.text import Text as RichText
            return Panel(RichText("No scan data available. Press 's' to scan.", style="dim"),
                        title="Channel Heatmap", border_style="blue")

        # Use all data, dates in descending order (newest first)
        display_channels = list(self.channels)
        display_dates = list(reversed(self.dates))
        display_data = np.flipud(self.data)  # Flip rows to match reversed dates

        # Calculate vertical padding to expand rows to fill height
        # Reserve: panel border (2) + header row (1) + legend (1) + info (1) + help (1) = 6
        available_height = console_height - 6
        num_rows = len(display_dates) + 1  # +1 for header
        if num_rows > 0 and available_height > num_rows:
            row_padding = max(0, (available_height - num_rows) // (num_rows * 2))
        else:
            row_padding = 0

        # Create heatmap table that expands to fill width and height
        table = Table(
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
            padding=(0, 1),
            expand=True,
        )

        # Add date column
        table.add_column("", style="dim", no_wrap=True)

        # Add channel columns (no fixed width - let them expand)
        for ch in display_channels:
            table.add_column(str(ch), justify="center", no_wrap=True)

        # Calculate cell height (1 + padding top + padding bottom)
        cell_height = 1 + (row_padding * 2)

        # Add rows for each date
        for row_idx, date_str in enumerate(display_dates):
            # Format date (short format to fit column)
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                date_label = dt.strftime("%m/%d")
            except ValueError:
                date_label = date_str[:6]

            # Repeat date label vertically to fill cell height
            date_cell = Text("\n".join([date_label] + [""] * (cell_height - 1)))

            # Build row cells
            cells = [date_cell]
            for col_idx in range(len(display_channels)):
                count = display_data[row_idx, col_idx]

                if np.isnan(count):
                    block = "░"
                    color = "dim"
                else:
                    count_int = int(count)
                    color = get_congestion_color(count_int)

                    if count_int == 0:
                        block = "░"
                    elif count_int <= 2:
                        block = "▒"
                    elif count_int <= 4:
                        block = "▓"
                    else:
                        block = "█"

                # Repeat block vertically to fill cell height
                cell = Text("\n".join([block] * cell_height), style=color)
                cells.append(cell)

            table.add_row(*cells)

        # Create legend
        legend = Text()
        legend.append("Legend: ", style="dim")
        legend.append("░", style="dim")
        legend.append(" none  ", style="dim")
        legend.append("░", style="green")
        legend.append(" clear  ", style="dim")
        legend.append("▒", style="yellow")
        legend.append(" light  ", style="dim")
        legend.append("▓", style="dark_orange")
        legend.append(" moderate  ", style="dim")
        legend.append("█", style="red")
        legend.append(" congested", style="dim")

        # Create info bar - just show last scan time
        info_text = Text()
        if self.last_scan_time:
            ago = (datetime.now() - self.last_scan_time).total_seconds()
            if ago < 60:
                time_str = f"{int(ago)}s ago"
            elif ago < 3600:
                time_str = f"{int(ago / 60)}m ago"
            else:
                time_str = f"{int(ago / 3600)}h ago"
            info_text.append(f"Last scan: {time_str}", style="dim")
        else:
            info_text.append("No scan data", style="dim red")

        # Build the panel with height to fill available space
        title = f"Channel Heatmap ({self.band}GHz) - Last {self.days} days"

        # Calculate panel height (total height minus footer lines)
        panel_height = max(5, console_height - 4)

        heatmap_panel = Panel(
            table,
            title=title,
            border_style="blue",
            height=panel_height,
        )

        help_bar = create_help_bar("heatmap")

        # Compose as Group
        return Group(
            heatmap_panel,
            Align.center(legend),
            Align.center(info_text),
            help_bar,
        )

    def handle_key(self, key):
        """
        Handle keypress for heatmap view.

        Returns:
            str or None: 'quit', 'live', or None to stay in view
        """
        if key == 'q':
            return 'quit'
        elif key == 'l':
            return 'live'
        elif key == '7':
            self.days = 7
            self.load_data()
        elif key == '1':
            self.days = 14
            self.load_data()
        elif key == '3':
            self.days = 30
            self.load_data()
        elif key == '2':
            self.band = "2.4"
            self.load_data()
        elif key == '5':
            self.band = "5"
            self.load_data()
        elif key == 's':
            self.trigger_scan()

        return None
