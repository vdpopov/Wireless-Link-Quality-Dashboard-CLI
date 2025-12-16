"""Entry point for wifi-monitor-cli."""

import argparse
import sys

from rich.console import Console

from . import __version__
from .app import App, select_interface


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Terminal-based WiFi link and latency monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Controls:
  Live View:
    q       Quit
    h       Switch to heatmap view
    p       Pause/resume data collection
    +/-     Change time window
    a       Add ping host
    d       Delete ping host

  Heatmap View:
    q       Quit
    l       Switch to live view
    7/1/3   Set days (7/14/30)
    2/5     Set band (2.4GHz/5GHz)
    s       Trigger new scan
""",
    )

    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"wifi-monitor-cli {__version__}",
    )

    parser.add_argument(
        "-i", "--interface",
        help="WiFi interface to use (auto-detected if not specified)",
    )

    parser.add_argument(
        "-r", "--refresh",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    console = Console()

    # Check for required tools
    try:
        import subprocess
        subprocess.run(["iw", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]Error: 'iw' command not found![/red]")
        console.print("[dim]Install it with: sudo apt install iw (Debian/Ubuntu)[/dim]")
        console.print("[dim]              or: sudo pacman -S iw (Arch)[/dim]")
        sys.exit(1)

    # Banner
    console.print()
    console.print("[bold cyan]WiFi Monitor CLI[/bold cyan]", justify="center")
    console.print(f"[dim]v{__version__}[/dim]", justify="center")
    console.print()

    # Select or use provided interface
    if args.interface:
        interface = args.interface
        console.print(f"[green]Using interface: {interface}[/green]")
    else:
        interface = select_interface()

    console.print()
    console.print("[dim]Starting monitor... Press 'q' to quit.[/dim]")
    console.print()

    # Set refresh interval
    from . import config
    config.REFRESH_INTERVAL = args.refresh

    # Run the app
    try:
        app = App(interface)
        app.run()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
