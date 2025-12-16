"""Simple chart rendering using Unicode characters."""

import numpy as np


# Sparkline characters - 5/8 width blocks (thin look)
SPARK_CHARS = " ▋▋▋▋▋▋▋▋"


def resample_data(data, target_width):
    """
    Resample data to fit exactly target_width points.

    If data has more points than target_width, compress by averaging buckets.
    If data has fewer points, pad from left with NaN.
    """
    if len(data) == 0:
        return np.full(target_width, np.nan)

    data = np.asarray(data, dtype=float)

    if len(data) == target_width:
        return data
    elif len(data) < target_width:
        # Pad from left with NaN
        padding = np.full(target_width - len(data), np.nan)
        return np.concatenate([padding, data])
    else:
        # Compress by averaging buckets
        # Split data into target_width buckets and average each
        result = np.zeros(target_width)
        bucket_size = len(data) / target_width
        for i in range(target_width):
            start = int(i * bucket_size)
            end = int((i + 1) * bucket_size)
            bucket = data[start:end]
            valid = bucket[~np.isnan(bucket)]
            if len(valid) > 0:
                result[i] = np.mean(valid)
            else:
                result[i] = np.nan
        return result


def bucket_by_time(values, timestamps, window_seconds, target_width, now=None):
    """
    Bucket data by fixed time slots for stable chart rendering.

    Args:
        values: Array of data values
        timestamps: Array of timestamps for each value
        window_seconds: Total time window in seconds
        target_width: Number of buckets (chart columns)
        now: Current timestamp (if None, uses time.time())

    Returns:
        Array of target_width values, with NaN for empty buckets
    """
    import time as time_module

    if len(values) == 0 or len(timestamps) == 0:
        return np.full(target_width, np.nan)

    values = np.asarray(values, dtype=float)
    timestamps = np.asarray(timestamps, dtype=float)

    bucket_duration = window_seconds / target_width
    if now is None:
        now = time_module.time()

    # Align window_end to bucket boundary (snap to nearest bucket)
    window_end = np.ceil(now / bucket_duration) * bucket_duration
    window_start = window_end - window_seconds

    result = np.full(target_width, np.nan)

    for i in range(target_width):
        bucket_start = window_start + i * bucket_duration
        bucket_end = bucket_start + bucket_duration

        # Find values in this time bucket
        mask = (timestamps >= bucket_start) & (timestamps < bucket_end)
        bucket_values = values[mask]
        valid = bucket_values[~np.isnan(bucket_values)]

        if len(valid) > 0:
            result[i] = np.mean(valid)

    return result

# For 2-row sparklines: empty, lower, upper, full
# Row 0 (bottom): space=0-3, ▄=4-7, █=8-15
# Row 1 (top): space=0-7, ▄=8-11, █=12-15
HALF_BLOCK_LOWER = "▄"
HALF_BLOCK_UPPER = "▀"
FULL_BLOCK = "▋"


def sparkline(data, width=50, color_func=None):
    """
    Render data as a sparkline using Unicode block characters.

    Args:
        data: Array of numeric values
        width: Output width in characters
        color_func: Optional function(value) -> color name for each point

    Returns:
        str or list: Sparkline string, or list of (char, color) tuples if color_func provided
    """
    if len(data) == 0:
        if color_func:
            return [("─", "dim")] * width
        return "─" * width

    data = np.asarray(data, dtype=float)

    # Filter NaN values
    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask):
        if color_func:
            return [("─", "dim")] * width
        return "─" * width

    # Get only the last 'width' points, or pad if fewer
    original_data = data.copy()
    if len(data) > width:
        data = data[-width:]
        original_data = original_data[-width:]

    # For display, replace NaN with interpolated or min value
    clean_data = data.copy()
    valid_vals = clean_data[~np.isnan(clean_data)]
    if len(valid_vals) > 0:
        min_val = np.min(valid_vals)
        clean_data[np.isnan(clean_data)] = min_val
    else:
        if color_func:
            return [("─", "dim")] * width
        return "─" * width

    # Normalize to 0-8 range
    min_val = np.min(clean_data)
    max_val = np.max(clean_data)

    if max_val == min_val:
        normalized = np.full(len(clean_data), 4, dtype=int)
    else:
        normalized = ((clean_data - min_val) / (max_val - min_val) * 8).astype(int)
        normalized = np.clip(normalized, 0, 8)

    if color_func:
        # Return list of (char, color) tuples for colored output
        result = []
        # Pad from left if needed
        if len(normalized) < width:
            pad_count = width - len(normalized)
            result.extend([(" ", "dim")] * pad_count)

        for i, n in enumerate(normalized):
            char = SPARK_CHARS[n]
            orig_val = original_data[i] if i < len(original_data) else None
            if orig_val is not None and not np.isnan(orig_val):
                color = color_func(orig_val)
            else:
                color = "dim"
            result.append((char, color))
        return result
    else:
        result = "".join(SPARK_CHARS[n] for n in normalized)
        # Pad to width if shorter
        if len(result) < width:
            result = " " * (width - len(result)) + result
        return result


def multi_sparkline(data, width=50, height=4, color_func=None, fixed_min=None, fixed_max=None):
    """
    Render data as a multi-row sparkline with high vertical resolution.

    Uses block characters to achieve (height * 8) levels.

    Args:
        data: Array of numeric values
        width: Output width in characters
        height: Number of rows (default 4)
        color_func: Optional function(value) -> color name for each point
        fixed_min: Fixed minimum value for scaling (prevents rescaling)
        fixed_max: Fixed maximum value for scaling (prevents rescaling)

    Returns:
        list: List of rows (top to bottom), each is list of (char, color) tuples
    """
    empty_row = [(" ", "dim")] * width

    if len(data) == 0:
        return [empty_row] * height

    data = np.asarray(data, dtype=float)

    # Track which values are NaN (to render as empty space)
    nan_mask = np.isnan(data)

    # Filter NaN values
    if not np.any(~nan_mask):
        return [empty_row] * height

    # Get only the last 'width' points, or pad if fewer
    original_data = data.copy()
    if len(data) > width:
        data = data[-width:]
        original_data = original_data[-width:]
        nan_mask = nan_mask[-width:]

    # For display, replace NaN with min value (but we'll render them as empty)
    clean_data = data.copy()
    valid_vals = clean_data[~nan_mask]
    if len(valid_vals) > 0:
        data_min = np.min(valid_vals)
        clean_data[nan_mask] = data_min
    else:
        return [empty_row] * height

    # Use fixed range if provided, otherwise use data range
    min_val = fixed_min if fixed_min is not None else np.min(clean_data)
    max_val = fixed_max if fixed_max is not None else np.max(clean_data)

    # Clamp data to fixed range
    clean_data = np.clip(clean_data, min_val, max_val)
    max_level = height * 8 - 1

    if max_val == min_val:
        normalized = np.full(len(clean_data), max_level // 2, dtype=int)
    else:
        normalized = ((clean_data - min_val) / (max_val - min_val) * max_level).astype(int)
        normalized = np.clip(normalized, 0, max_level)

    # Build rows (from top to bottom)
    rows = [[] for _ in range(height)]

    # Pad from left if needed
    if len(normalized) < width:
        pad_count = width - len(normalized)
        for row in rows:
            row.extend([(" ", "dim")] * pad_count)

    for i, n in enumerate(normalized):
        # Check if this value was originally NaN - render as empty space
        is_nan = nan_mask[i] if i < len(nan_mask) else True

        if is_nan:
            # Empty bucket - render as empty space in all rows
            for row_idx in range(height):
                rows[row_idx].append((" ", "dim"))
            continue

        orig_val = original_data[i] if i < len(original_data) else None
        if color_func and orig_val is not None:
            color = color_func(orig_val)
        else:
            color = "cyan"

        # For each row, determine what character to show
        # Row 0 is top (highest values), row height-1 is bottom (lowest values)
        for row_idx in range(height):
            # This row covers levels from row_min to row_max
            row_from_bottom = height - 1 - row_idx
            row_min = row_from_bottom * 8
            row_max = row_min + 7

            if n < row_min:
                # Value is below this row
                rows[row_idx].append((" ", "dim"))
            elif n >= row_max:
                # Value fills this entire row
                rows[row_idx].append((FULL_BLOCK, color))
            else:
                # Value is partially in this row
                level_in_row = n - row_min
                rows[row_idx].append((SPARK_CHARS[level_in_row + 1], color))

    return rows


def multi_sparkline_overlay(data1, data2, width=50, height=4, color1="green", color2="blue", fixed_min=None, fixed_max=None):
    """
    Render two data series overlaid on the same chart.

    data1 (RX/green) is the base layer, data2 (TX/blue) overlays from the bottom.
    Visual result: TX (blue) fills from bottom to TX level, RX (green) fills
    from TX level to RX level (showing where RX exceeds TX).

    Args:
        data1: First data series (RX - typically higher)
        data2: Second data series (TX - typically lower, shown at bottom)
        width: Output width in characters
        height: Number of rows
        color1: Color for first series (green for RX)
        color2: Color for second series (blue for TX)
        fixed_min: Fixed minimum value for scaling
        fixed_max: Fixed maximum value for scaling

    Returns:
        list: List of rows (top to bottom), each is list of (char, color) tuples
    """
    empty_row = [(" ", "dim")] * width

    data1 = np.asarray(data1, dtype=float) if len(data1) > 0 else np.array([])
    data2 = np.asarray(data2, dtype=float) if len(data2) > 0 else np.array([])

    if len(data1) == 0 and len(data2) == 0:
        return [empty_row] * height

    # Track NaN masks
    nan_mask1 = np.isnan(data1) if len(data1) > 0 else np.array([])
    nan_mask2 = np.isnan(data2) if len(data2) > 0 else np.array([])

    # Truncate to width
    if len(data1) > width:
        data1 = data1[-width:]
        nan_mask1 = nan_mask1[-width:]
    if len(data2) > width:
        data2 = data2[-width:]
        nan_mask2 = nan_mask2[-width:]

    # Pad to same length
    max_len = max(len(data1), len(data2))
    if len(data1) < max_len:
        pad = np.full(max_len - len(data1), np.nan)
        data1 = np.concatenate([pad, data1])
        nan_mask1 = np.concatenate([np.ones(max_len - len(nan_mask1), dtype=bool), nan_mask1])
    if len(data2) < max_len:
        pad = np.full(max_len - len(data2), np.nan)
        data2 = np.concatenate([pad, data2])
        nan_mask2 = np.concatenate([np.ones(max_len - len(nan_mask2), dtype=bool), nan_mask2])

    # Get valid data for range calculation
    all_valid = np.concatenate([data1[~nan_mask1], data2[~nan_mask2]])
    if len(all_valid) == 0:
        return [empty_row] * height

    # Determine range
    min_val = fixed_min if fixed_min is not None else np.min(all_valid)
    max_val = fixed_max if fixed_max is not None else np.max(all_valid)

    # Replace NaN with min for calculation
    clean1 = np.where(nan_mask1, min_val, np.clip(data1, min_val, max_val))
    clean2 = np.where(nan_mask2, min_val, np.clip(data2, min_val, max_val))

    # Normalize to levels
    max_level = height * 8 - 1
    if max_val == min_val:
        norm1 = np.full(len(clean1), max_level // 2, dtype=int)
        norm2 = np.full(len(clean2), max_level // 2, dtype=int)
    else:
        norm1 = ((clean1 - min_val) / (max_val - min_val) * max_level).astype(int)
        norm2 = ((clean2 - min_val) / (max_val - min_val) * max_level).astype(int)
        norm1 = np.clip(norm1, 0, max_level)
        norm2 = np.clip(norm2, 0, max_level)

    # Build rows
    rows = [[] for _ in range(height)]

    # Pad from left if needed
    if len(norm1) < width:
        pad_count = width - len(norm1)
        for row in rows:
            row.extend([(" ", "dim")] * pad_count)

    for i in range(len(norm1)):
        is_nan1 = nan_mask1[i]
        is_nan2 = nan_mask2[i]
        n1 = norm1[i] if not is_nan1 else -1  # RX level (typically higher)
        n2 = norm2[i] if not is_nan2 else -1  # TX level (typically lower)

        for row_idx in range(height):
            row_from_bottom = height - 1 - row_idx
            row_min = row_from_bottom * 8
            row_max = row_min + 7

            # Overlay: TX (blue) on bottom, RX (green) on top
            # Show whichever is the "top" value at each row

            if n1 < row_min and n2 < row_min:
                # Neither reaches this row
                char, color = " ", "dim"
            elif n2 >= row_max:
                # TX fully covers this row (blue base)
                char, color = FULL_BLOCK, color2
            elif n2 >= row_min and n1 <= n2:
                # TX partially in row, RX doesn't exceed TX
                level = n2 - row_min
                char, color = SPARK_CHARS[level + 1], color2
            elif n1 >= row_max:
                # RX fully covers this row (green on top)
                char, color = FULL_BLOCK, color1
            elif n1 >= row_min:
                # RX partially in row
                level = n1 - row_min
                char, color = SPARK_CHARS[level + 1], color1
            else:
                char, color = " ", "dim"

            rows[row_idx].append((char, color))

    return rows


def double_sparkline(data, width=50, color_func=None):
    """
    Render data as a 2-row sparkline with double vertical resolution.
    Wrapper around multi_sparkline for backwards compatibility.
    """
    rows = multi_sparkline(data, width=width, height=2, color_func=color_func)
    return (rows[0], rows[1])


def tall_sparkline(data, width=50, height=4):
    """
    Render data as a multi-line sparkline using braille characters (line style).

    Args:
        data: Array of numeric values
        width: Output width in characters
        height: Number of lines (each braille char is 4 dots tall)

    Returns:
        list[str]: List of strings, one per line (top to bottom)
    """
    if len(data) == 0:
        return [" " * width] * height

    data = np.asarray(data, dtype=float)

    # Filter NaN values
    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask):
        return [" " * width] * height

    # Resample data to fit width (2 data points per braille char)
    target_points = width * 2
    if len(data) > target_points:
        # Downsample
        indices = np.linspace(0, len(data) - 1, target_points, dtype=int)
        data = data[indices]
    elif len(data) < target_points:
        # Pad from left with NaN
        padding = np.full(target_points - len(data), np.nan)
        data = np.concatenate([padding, data])

    # Track which points are valid (not NaN)
    valid = ~np.isnan(data)

    # Replace NaN with 0 for calculations but track validity
    valid_vals = data[valid]
    if len(valid_vals) == 0:
        return [" " * width] * height

    min_val = np.min(valid_vals)
    max_val = np.max(valid_vals)
    data = np.where(np.isnan(data), min_val, data)

    # Normalize to 0 to (height * 4 - 1) range
    max_dot_row = height * 4 - 1
    if max_val == min_val:
        normalized = np.full(len(data), max_dot_row // 2)
    else:
        normalized = ((data - min_val) / (max_val - min_val) * max_dot_row).astype(int)
        normalized = np.clip(normalized, 0, max_dot_row)

    # Braille dot bit positions
    # Left column: dots 1,2,3,7 (top to bottom) = bits 0,1,2,6
    # Right column: dots 4,5,6,8 (top to bottom) = bits 3,4,5,7
    left_bits = [0, 1, 2, 6]
    right_bits = [3, 4, 5, 7]

    # Build the braille characters - LINE style (only light up dots at the value level)
    chars_per_line = [[] for _ in range(height)]

    for i in range(0, len(normalized), 2):
        left_val = normalized[i]
        right_val = normalized[i + 1] if i + 1 < len(normalized) else normalized[i]
        left_valid = valid[i]
        right_valid = valid[i + 1] if i + 1 < len(valid) else valid[i]

        for line_idx in range(height):
            # This line covers dot rows from base_row to base_row + 3
            # (top line = highest values, so we invert)
            base_row = (height - 1 - line_idx) * 4

            dots = 0

            # Left column - light up the dot(s) at the value level
            if left_valid:
                for dot_idx, bit in enumerate(left_bits):
                    dot_row = base_row + dot_idx
                    # Light up if value is at this row (with some thickness for visibility)
                    if abs(left_val - dot_row) <= 0:
                        dots |= (1 << bit)

            # Right column
            if right_valid:
                for dot_idx, bit in enumerate(right_bits):
                    dot_row = base_row + dot_idx
                    if abs(right_val - dot_row) <= 0:
                        dots |= (1 << bit)

            # Also connect vertically between left and right if they differ
            if left_valid and right_valid and left_val != right_val:
                low, high = min(left_val, right_val), max(left_val, right_val)
                for dot_idx, bit in enumerate(right_bits):
                    dot_row = base_row + dot_idx
                    if low <= dot_row <= high:
                        dots |= (1 << bit)

            chars_per_line[line_idx].append(chr(0x2800 + dots))

    return ["".join(chars) for chars in chars_per_line]


def progress_bar(value, min_val, max_val, width=20, filled="█", empty="░"):
    """
    Render a progress bar.

    Args:
        value: Current value
        min_val: Minimum value (0% of bar)
        max_val: Maximum value (100% of bar)
        width: Bar width in characters
        filled: Character for filled portion
        empty: Character for empty portion

    Returns:
        str: Progress bar string
    """
    if value is None or np.isnan(value):
        return empty * width

    # Clamp and normalize
    ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0, min(1, ratio))

    filled_count = int(ratio * width)
    empty_count = width - filled_count

    return filled * filled_count + empty * empty_count


def signal_quality(dbm):
    """
    Get signal quality description and color.

    Args:
        dbm: Signal strength in dBm

    Returns:
        tuple: (description, rich_color)
    """
    if dbm is None:
        return "No signal", "red"
    elif dbm >= -50:
        return "Excellent", "green"
    elif dbm >= -60:
        return "Good", "yellow"
    elif dbm >= -70:
        return "Fair", "dark_orange"
    else:
        return "Poor", "red"


def ping_quality(ms):
    """
    Get ping quality color.

    Args:
        ms: Latency in milliseconds

    Returns:
        str: rich color name
    """
    if ms is None:
        return "red"
    elif ms < 20:
        return "green"
    elif ms < 50:
        return "yellow"
    elif ms < 100:
        return "dark_orange"
    else:
        return "red"


def signal_color(dbm):
    """Get color for signal value (for sparkline coloring)."""
    if dbm is None or np.isnan(dbm):
        return "dim"
    elif dbm >= -50:
        return "green"
    elif dbm >= -60:
        return "yellow"
    elif dbm >= -70:
        return "dark_orange"
    else:
        return "red"


def ping_color(ms):
    """Get color for ping value (for sparkline coloring)."""
    if ms is None or np.isnan(ms):
        return "dim"
    elif ms < 20:
        return "green"
    elif ms < 50:
        return "yellow"
    elif ms < 100:
        return "dark_orange"
    else:
        return "red"


def format_duration(seconds):
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h"
    else:
        return f"{int(seconds / 86400)}d"


def get_congestion_color(count):
    """Get rich color name based on network count."""
    if count is None or (isinstance(count, float) and np.isnan(count)):
        return "dim"
    elif count == 0:
        return "green"
    elif count <= 2:
        return "yellow"
    elif count <= 4:
        return "dark_orange"
    else:
        return "red"
