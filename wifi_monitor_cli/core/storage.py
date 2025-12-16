"""Scan data persistence and heatmap data generation."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .. import config


STORAGE_DIR = config.SCAN_STORAGE_PATH


def ensure_storage_dir():
    """Create storage directory if it doesn't exist."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_today_file():
    """Get path to today's scan file."""
    return STORAGE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"


def save_scan(scan_data):
    """
    Save a scan to today's file.
    Appends to existing scans if file exists.
    """
    if scan_data is None:
        return False

    ensure_storage_dir()
    filepath = get_today_file()

    # Load existing scans for today
    scans = []
    if filepath.exists():
        try:
            with open(filepath, "r") as f:
                scans = json.load(f)
        except (json.JSONDecodeError, IOError):
            scans = []

    # Append new scan
    scans.append(scan_data)

    # Save back
    try:
        with open(filepath, "w") as f:
            json.dump(scans, f, indent=2)
        return True
    except IOError:
        return False


def load_day_scans(date):
    """
    Load all scans for a specific date.
    Returns list of scan dicts, or empty list if no data.
    """
    if isinstance(date, str):
        date_str = date
    else:
        date_str = date.strftime("%Y-%m-%d")

    filepath = STORAGE_DIR / f"{date_str}.json"

    if not filepath.exists():
        return []

    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def load_scans(days=7):
    """
    Load scans from the last N days.
    Returns dict: {date_str: [scan1, scan2, ...], ...}
    """
    result = {}
    today = datetime.now().date()

    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        scans = load_day_scans(date_str)
        if scans:
            result[date_str] = scans

    return result


def get_last_scan_time():
    """
    Get timestamp of the most recent scan.
    Returns datetime or None if no scans exist.
    """
    today = datetime.now().date()

    for i in range(30):
        date = today - timedelta(days=i)
        scans = load_day_scans(date)
        if scans:
            latest = max(scans, key=lambda s: s.get("timestamp", 0))
            return datetime.fromtimestamp(latest["timestamp"])

    return None


def _scan_total_networks(scan):
    """Count total networks found in a scan."""
    total = 0
    channels_data = scan.get("channels", {})
    for ch_data in channels_data.values():
        if isinstance(ch_data, dict):
            total += ch_data.get("count", 0)
    return total


def get_heatmap_data(days=7, band=None):
    """
    Build 2D numpy array for heatmap display.

    Args:
        days: Number of days to include
        band: '2.4' or '5' (auto-detected if None)

    Returns tuple: (data, dates, channels, band)
        - data: 2D array shape (days, num_channels) with network counts
        - dates: list of date strings (oldest first)
        - channels: list of channel numbers
        - band: the band used ('2.4' or '5')
    """
    from .scanner import get_channels_for_band
    from .net import get_current_band

    # Auto-detect band if not specified
    if band is None:
        band = get_current_band() or "2.4"

    channels = get_channels_for_band(band)
    today = datetime.now().date()

    # Build list of dates (oldest first)
    dates = []
    for i in range(days - 1, -1, -1):
        date = today - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))

    # Build data array
    data = np.zeros((len(dates), len(channels)), dtype=np.float32)

    for row_idx, date_str in enumerate(dates):
        scans = load_day_scans(date_str)
        if not scans:
            data[row_idx, :] = np.nan
            continue

        # Filter scans by band
        band_scans = [s for s in scans if s.get("band") == band]
        if not band_scans:
            if band == "2.4":
                band_scans = [s for s in scans if s.get("band") is None]

        if not band_scans:
            data[row_idx, :] = np.nan
            continue

        # Use the scan with most networks found
        best_scan = max(band_scans, key=_scan_total_networks)
        channels_data = best_scan.get("channels", {})

        for col_idx, ch in enumerate(channels):
            ch_data = channels_data.get(str(ch)) or channels_data.get(ch)
            if ch_data:
                data[row_idx, col_idx] = ch_data.get("count", 0)

    return data, dates, channels, band


def get_scan_dates():
    """
    Get list of dates that have scan data.
    Returns list of date strings, newest first.
    """
    if not STORAGE_DIR.exists():
        return []

    dates = []
    for filepath in STORAGE_DIR.glob("*.json"):
        date_str = filepath.stem
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            continue

    return sorted(dates, reverse=True)


def cleanup_old_scans(keep_days=90):
    """Remove scan files older than keep_days."""
    if not STORAGE_DIR.exists():
        return

    cutoff = datetime.now().date() - timedelta(days=keep_days)

    for filepath in STORAGE_DIR.glob("*.json"):
        try:
            date = datetime.strptime(filepath.stem, "%Y-%m-%d").date()
            if date < cutoff:
                filepath.unlink()
        except (ValueError, OSError):
            continue
