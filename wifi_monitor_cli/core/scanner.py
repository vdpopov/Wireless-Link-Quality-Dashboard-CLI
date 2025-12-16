"""WiFi channel scanning and congestion detection."""

import subprocess
import re
import time

from .. import config
from .net import get_current_band

# Channel definitions
CHANNELS_2_4GHZ = list(range(1, 15))  # 1-14
CHANNELS_5GHZ = [
    36, 40, 44, 48, 52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
    149, 153, 157, 161, 165
]

# Frequency to channel mapping for 5GHz (MHz -> channel)
FREQ_TO_CHANNEL_5GHZ = {
    5180: 36, 5200: 40, 5220: 44, 5240: 48,
    5260: 52, 5280: 56, 5300: 60, 5320: 64,
    5500: 100, 5520: 104, 5540: 108, 5560: 112,
    5580: 116, 5600: 120, 5620: 124, 5640: 128,
    5660: 132, 5680: 136, 5700: 140, 5720: 144,
    5745: 149, 5765: 153, 5785: 157, 5805: 161, 5825: 165,
}

# Frequency to channel for 2.4GHz
FREQ_TO_CHANNEL_2_4GHZ = {
    2412: 1, 2417: 2, 2422: 3, 2427: 4, 2432: 5, 2437: 6, 2442: 7,
    2447: 8, 2452: 9, 2457: 10, 2462: 11, 2467: 12, 2472: 13, 2484: 14,
}


def freq_to_channel(freq_mhz):
    """Convert frequency in MHz to channel number."""
    freq_int = int(freq_mhz)
    if freq_int in FREQ_TO_CHANNEL_5GHZ:
        return FREQ_TO_CHANNEL_5GHZ[freq_int]
    if freq_int in FREQ_TO_CHANNEL_2_4GHZ:
        return FREQ_TO_CHANNEL_2_4GHZ[freq_int]
    return None


def get_channels_for_band(band):
    """Get channel list for a band ('2.4' or '5')."""
    if band == "5":
        return CHANNELS_5GHZ
    return CHANNELS_2_4GHZ


def refresh_scan_cache():
    """
    Ask NetworkManager to refresh the WiFi scan cache.
    This is non-blocking and may take a few seconds to complete.
    """
    try:
        subprocess.run(
            ["nmcli", "device", "wifi", "rescan"],
            capture_output=True,
            timeout=5
        )
        time.sleep(2)
        return True
    except Exception:
        return False


def scan_channels(interface=None, refresh_cache=True, band=None):
    """
    Parse cached WiFi scan results to get channel congestion data.
    Uses 'iw dev <iface> scan dump' which doesn't require root.

    Args:
        interface: WiFi interface name (defaults to config.INTERFACE)
        refresh_cache: If True, trigger NetworkManager rescan first
        band: '2.4' or '5' (auto-detected from current connection if None)

    Returns dict with:
        {
            "timestamp": <unix_timestamp>,
            "band": "2.4" or "5",
            "channels": {
                1: {"count": 4, "networks": ["SSID1", "SSID2", ...]},
                ...
            }
        }
    Returns None if scan fails.
    """
    if interface is None:
        interface = config.INTERFACE

    if not interface:
        return None

    # Auto-detect band from current connection
    if band is None:
        band = get_current_band() or "2.4"

    channel_list = get_channels_for_band(band)

    # Refresh the cache before reading
    if refresh_cache:
        refresh_scan_cache()

    try:
        result = subprocess.check_output(
            ["iw", "dev", interface, "scan", "dump"],
            text=True,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        return None

    # Initialize channels for the detected band
    channels = {ch: {"count": 0, "networks": []} for ch in channel_list}

    # Parse BSS entries
    current_bss = None
    current_channel = None
    current_freq = None
    current_ssid = None

    for line in result.split("\n"):
        line = line.strip()

        # New BSS entry
        if line.startswith("BSS "):
            # Save previous entry
            final_channel = current_channel
            if final_channel is None and current_freq is not None:
                final_channel = freq_to_channel(current_freq)

            if final_channel is not None and final_channel in channels:
                channels[final_channel]["count"] += 1
                if current_ssid:
                    channels[final_channel]["networks"].append(current_ssid)

            current_bss = line.split()[1].split("(")[0]
            current_channel = None
            current_freq = None
            current_ssid = None
            continue

        # Extract frequency (fallback for channel detection)
        freq_match = re.match(r"freq: ([\d.]+)", line)
        if freq_match:
            current_freq = float(freq_match.group(1))
            continue

        # Extract channel from DS Parameter set (preferred)
        channel_match = re.match(r"DS Parameter set: channel (\d+)", line)
        if channel_match:
            current_channel = int(channel_match.group(1))
            continue

        # Extract SSID
        ssid_match = re.match(r"SSID: (.+)", line)
        if ssid_match:
            ssid = ssid_match.group(1).strip()
            if ssid:
                current_ssid = ssid
            continue

    # Don't forget the last entry
    final_channel = current_channel
    if final_channel is None and current_freq is not None:
        final_channel = freq_to_channel(current_freq)

    if final_channel is not None and final_channel in channels:
        channels[final_channel]["count"] += 1
        if current_ssid:
            channels[final_channel]["networks"].append(current_ssid)

    # Deduplicate networks per channel
    for ch in channels:
        channels[ch]["networks"] = list(set(channels[ch]["networks"]))
        channels[ch]["count"] = len(channels[ch]["networks"]) or channels[ch]["count"]

    return {
        "timestamp": int(time.time()),
        "band": band,
        "channels": channels
    }


def get_channel_counts(interface=None):
    """
    Simplified version that returns just channel -> count mapping.
    Returns dict like {1: 4, 2: 0, 3: 1, ...} or None on failure.
    """
    scan = scan_channels(interface)
    if scan is None:
        return None

    return {ch: data["count"] for ch, data in scan["channels"].items()}
