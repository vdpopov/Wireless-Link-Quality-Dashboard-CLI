"""Data processing utilities."""

import numpy as np


def smooth_data(data, alpha=0.3):
    """
    Apply exponential moving average smoothing to data.

    Args:
        data: Input array (may contain NaN values)
        alpha: Smoothing factor (0-1), higher = less smoothing

    Returns:
        Smoothed array with NaN values preserved
    """
    if len(data) == 0:
        return data

    data = np.asarray(data, dtype=float)
    smoothed = np.empty_like(data)

    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask):
        return data

    first_valid_idx = np.argmax(valid_mask)
    ema = data[first_valid_idx]

    for i in range(len(data)):
        if np.isnan(data[i]):
            smoothed[i] = np.nan
        else:
            if i == first_valid_idx:
                ema = data[i]
            else:
                ema = alpha * data[i] + (1 - alpha) * ema
            smoothed[i] = ema

    return smoothed
