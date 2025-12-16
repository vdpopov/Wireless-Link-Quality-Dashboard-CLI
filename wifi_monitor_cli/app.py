"""Main application class with event loop and view management."""

import time
import sys
import threading

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from . import config
from .core import net, ping, scanner, storage
from .ui.keyboard import KeyboardHandler
from .ui.live_view import LiveView
from .ui.heatmap_view import HeatmapView

# Background scan interval (1 hour)
SCAN_INTERVAL = 3600


class App:
    """Main application class."""

    def __init__(self, interface):
        self.console = Console()
        self.keyboard = KeyboardHandler()
        self.interface = interface
        self.running = True
        self.current_view = "live"

        # Initialize views
        self.live_view = LiveView()
        self.heatmap_view = HeatmapView()

        # Set interface in config
        config.INTERFACE = interface

        # Background scan thread
        self.scan_thread = None
        self.last_scan_time = 0

        # Background data collection
        self.collect_thread = None
        self.collecting = True

    def setup_ping_hosts(self):
        """Set up default ping hosts (gateway and 1.1.1.1)."""
        # Add gateway
        gateway = net.get_default_gateway()
        if gateway:
            host_info = ping.add_ping_host(gateway, label="gateway")
            ping.gateway_host_info = host_info

        # Add 1.1.1.1 for internet connectivity check
        ping.add_ping_host("1.1.1.1", label="internet")

    def background_scan(self):
        """Perform a background channel scan."""
        try:
            # Get current band
            band = net.get_current_band() or "2.4"
            scan_result = scanner.scan_channels(band=band)
            if scan_result:
                storage.save_scan(scan_result)
                # Reload heatmap data
                self.heatmap_view.data = None
        except Exception:
            pass  # Silently fail - don't crash the app

    def check_and_run_scan(self):
        """Check if it's time for a scan and run it in background."""
        current_time = time.time()
        if current_time - self.last_scan_time >= SCAN_INTERVAL:
            self.last_scan_time = current_time
            # Run scan in background thread
            if self.scan_thread is None or not self.scan_thread.is_alive():
                self.scan_thread = threading.Thread(target=self.background_scan, daemon=True)
                self.scan_thread.start()

    def collection_worker(self):
        """Background worker for data collection."""
        while self.collecting:
            if not config.paused:
                self.live_view.collect_data()
                self.check_and_run_scan()
            time.sleep(config.REFRESH_INTERVAL)

    def start_collection(self):
        """Start background data collection."""
        self.collect_thread = threading.Thread(target=self.collection_worker, daemon=True)
        self.collect_thread.start()

    def stop_collection(self):
        """Stop background data collection."""
        self.collecting = False

    def add_ping_host_interactive(self):
        """Interactively add a new ping host."""
        self.keyboard.disable_raw_mode()
        try:
            self.console.print()
            host = Prompt.ask("[cyan]Enter host to ping (IP or hostname)[/cyan]")
            if host and host.strip():
                host = host.strip()
                ping.add_ping_host(host)
                self.console.print(f"[green]Added {host}[/green]")
            time.sleep(0.5)
        finally:
            self.keyboard.enable_raw_mode()

    def delete_ping_host_interactive(self):
        """Interactively delete a ping host."""
        if len(config.ping_hosts) == 0:
            return

        self.keyboard.disable_raw_mode()
        try:
            self.console.print()
            self.console.print("[cyan]Ping hosts:[/cyan]")
            for i, host in enumerate(config.ping_hosts):
                label = host.get("label", host.get("host"))
                self.console.print(f"  {i + 1}. {label}")

            choice = Prompt.ask(
                "[cyan]Enter number to delete (or empty to cancel)[/cyan]",
                default=""
            )
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(config.ping_hosts):
                    host = config.ping_hosts[idx]
                    label = host.get("label", host.get("host"))
                    ping.remove_ping_host(idx)
                    self.console.print(f"[yellow]Removed {label}[/yellow]")
            time.sleep(0.5)
        finally:
            self.keyboard.enable_raw_mode()

    def handle_input(self, key):
        """Handle keyboard input and return action."""
        if key is None:
            return None

        if self.current_view == "live":
            action = self.live_view.handle_key(key)
        else:
            action = self.heatmap_view.handle_key(key)

        if action == 'quit':
            self.running = False
        elif action == 'heatmap':
            self.current_view = "heatmap"
        elif action == 'live':
            self.current_view = "live"
        elif action == 'add_host':
            return 'add_host'
        elif action == 'delete_host':
            return 'delete_host'

        return action

    def render(self):
        """Render the current view."""
        size = self.console.size
        if self.current_view == "live":
            return self.live_view.render(size.width, size.height)
        else:
            return self.heatmap_view.render(size.width, size.height)

    def run(self):
        """Main application loop."""
        self.setup_ping_hosts()

        # Initial data collection
        self.live_view.collect_data()

        # Run initial scan in background
        self.last_scan_time = time.time() - SCAN_INTERVAL  # Force immediate scan

        # Start background data collection thread
        self.start_collection()

        with self.keyboard.raw_mode():
            with Live(
                self.render(),
                console=self.console,
                refresh_per_second=4,
                screen=True,
            ) as live:
                while self.running:
                    # Handle keyboard input
                    key = self.keyboard.get_key(timeout=0.1)
                    action = self.handle_input(key)

                    # Handle special actions that need input
                    if action == 'add_host':
                        live.stop()
                        self.add_ping_host_interactive()
                        live.start()
                    elif action == 'delete_host':
                        live.stop()
                        self.delete_ping_host_interactive()
                        live.start()

                    # Update display
                    live.update(self.render())

        # Cleanup
        self.stop_collection()
        ping.stop_all_ping_threads()
        self.console.print("[dim]Goodbye![/dim]")


def select_interface():
    """Show interface selection dialog."""
    console = Console()
    interfaces = net.get_wireless_interfaces()

    if not interfaces:
        console.print("[red]No wireless interfaces found![/red]")
        console.print("[dim]Make sure you have a WiFi adapter and 'iw' is installed.[/dim]")
        sys.exit(1)

    if len(interfaces) == 1:
        console.print(f"[green]Using interface: {interfaces[0]}[/green]")
        return interfaces[0]

    console.print("[cyan]Available wireless interfaces:[/cyan]")
    for i, iface in enumerate(interfaces):
        console.print(f"  {i + 1}. {iface}")

    choice = Prompt.ask(
        "[cyan]Select interface[/cyan]",
        default="1"
    )

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(interfaces):
            return interfaces[idx]
    except ValueError:
        pass

    return interfaces[0]
