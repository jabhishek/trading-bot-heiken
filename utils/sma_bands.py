import numpy as np
import pandas as pd
from collections.abc import Callable

from utils.no_op import no_op


def check_within_bands(
        sma_series: pd.Series,
        latest_price: float,
        desc: pd.Series,
        limit: str,
        logger: Callable[[str], None]
) -> bool:
    """
    Check if the current price is within the specified statistical band around SMA200.
    
    This function calculates upper and lower bands based on historical price deviations
    from SMA200 and checks if the current price falls within these bands. The bands
    are calculated using percentile-based statistical analysis of price deviations.
    
    The function is used to:
    1. Calculate statistical bands at different percentiles (25%, 50%, 75%, 80%, 85%, 90%, 95%)
    2. Determine the current price's position relative to these bands
    3. Provide information for position sizing and risk management decisions
    """
    # Get the band limit from statistical description
    band_limit = desc[limit]

    # Calculate upper and lower bands around SMA200
    upper_band_series = sma_series * (1 + band_limit)
    lower_band_series = sma_series * (1 - band_limit)

    # Get current band limits
    upper_band_limit = upper_band_series.iloc[-1]
    lower_band_limit = lower_band_series.iloc[-1]

    # Check if price is within bands
    above_upper_band = latest_price > upper_band_limit
    below_lower_band = latest_price < lower_band_limit
    within_band_limit = not above_upper_band and not below_lower_band

    # Log band analysis
    logger(
        f"limit: {limit}, "
        f"band_limit: {round(band_limit, 5)}, "
        f"within_band_limit: {within_band_limit}, "
        f"upper_band_limit: {round(upper_band_limit, 3)}, "
        f"lower_band_limit: {round(lower_band_limit, 3)}, "
        f"latest_price: {latest_price}"
    )

    return within_band_limit


def check_band_position(
        df: pd.DataFrame,
        latest_price: float,
        sma_period: int = 200,
        logger: Callable[[str], None] = None):
    price_series = df["mid_c"]
    sma_series = price_series.rolling(window=sma_period).mean()

    # get an array of all numbers between 0.01 and 1 with an increment of 0.01.
    numbers = np.arange(0.01, 1, 0.01)
    # Calculate percentage difference between price and SMA200
    diff_series = np.abs(price_series - sma_series) / sma_series
    desc = diff_series.describe(percentiles=numbers)

    # get the place in the band array
    for i in numbers:
        band = int(i * 100)
        # print(f"checking for {band}%")
        within_band = check_within_bands(sma_series, latest_price, desc, f"{band}%", no_op)
        if within_band:
            return i
    return None
