# heiken_ashi.py
import numpy as np
import pandas as pd

TOL = 1e-8

def ohlc_to_heiken_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert ordinary OHLC candles to Heiken-Ashi.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['time', 'mid_o', 'mid_h', 'mid_l', 'mid_c'].
        Index can be anything (datetime, int, etc.).

    Returns
    -------
    pd.DataFrame
        Columns: ['time', 'ha_open', 'ha_high', 'ha_low', 'ha_close']
        Index is preserved from the original DataFrame.
    """
    # Make a local copy with unified lower-case column names
    ohlc = df[['time', 'mid_o', 'mid_h', 'mid_l', 'mid_c']].copy()

    # Heiken-Ashi close: average of the four prices
    ha_close = ohlc[['mid_o', 'mid_h', 'mid_l', 'mid_c']].mean(axis=1)

    # Pre-allocate the HA open column
    ha_open = ha_close.copy()
    ha_open.iloc[0] = ohlc.loc[ohlc.index[0], 'mid_o']  # seed with original open

    # Iteratively fill subsequent HA opens
    for i in range(1, len(ohlc)):
        ha_open.iloc[i] = 0.5 * (ha_open.iloc[i - 1] + ha_close.iloc[i - 1])

    # HA high / low use the max / min of (ha_open, ha_close, high/low)
    ha_high = pd.concat([ha_open, ha_close, ohlc['mid_h']], axis=1).max(axis=1)
    ha_low = pd.concat([ha_open, ha_close, ohlc['mid_l']], axis=1).min(axis=1)
    # Candle colour -----------------------------------------------------------
    ha_green = ha_close > ha_open  # True  = bullish, False = bearish

    # Streak length -----------------------------------------------------------
    # Every time the colour flips, start a new group ID
    colour_change_id = (ha_green != ha_green.shift()).cumsum()

    # Within each group, count consecutive rows (starts at 0, so add 1)
    run_length = colour_change_id.groupby(colour_change_id).cumcount() + 1

    # Encode direction with sign: +n for green, -n for red
    direction = ha_green.mul(2).sub(1).astype("int8")
    ha_streak = run_length * direction

    ha_open_at_extreme = (
            (ha_green & (np.abs(ha_open - ha_low) < TOL)) |  # bullish: open == low
            (~ha_green & (np.abs(ha_open - ha_high) < TOL))  # bearish: open == high
    )

    ha_df = pd.DataFrame({
        'time': ohlc['time'],
        'ha_open': ha_open,
        'ha_high': ha_high,
        'ha_low': ha_low,
        'ha_close': ha_close,
        'ha_green': ha_green.astype(int),
        'ha_streak': ha_streak,
        'ha_open_at_extreme': ha_open_at_extreme.astype(int),
    }, index=df.index)

    return ha_df