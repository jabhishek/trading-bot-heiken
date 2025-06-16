import numpy as np
import pandas as pd

def convert_series_to_signals(series: pd.Series) -> pd.Series:
    # Create a DataFrame to hold the data
    df = pd.DataFrame({
        'series': series
    })

    # Calculate the change in series values
    df['series_change'] = df['series'].diff()

    # Determine if series is increasing or decreasing
    df['trend'] = np.where(df['series_change'] > 0, 1,
                          np.where(df['series_change'] < 0, -1, 0))

    # Forward fill zeros to carry forward the last known trend
    df['trend'] = df['trend'].replace(0, np.nan).ffill()

    return df['trend']


def calculate_trix(
        prices: pd.Series,
        period: int,
) -> pd.Series:
    # Calculate the first EMA
    ema1 = prices.ewm(span=period, adjust=False).mean()

    # Calculate the second EMA (EMA of EMA1)
    ema2 = ema1.ewm(span=period, adjust=False).mean()

    # Calculate the third EMA (EMA of EMA2)
    ema3 = ema2.ewm(span=period, adjust=False).mean()

    # Calculate TRIX as the 1-period percent change in the triple EMA
    trix_values = ema3.pct_change(periods=1) * 100

    return trix_values