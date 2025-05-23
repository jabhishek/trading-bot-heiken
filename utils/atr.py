import pandas as pd


def compute_atr(df: pd.DataFrame, close_field="mid_c", high_field="mid_h", low_field="mid_l", period=14):
    """
    Computes the Average True Range (ATR) over the specified period.
    """
    prev_c = df[close_field].shift(1)
    tr1 = df[high_field] - df[low_field]
    tr2 = abs(df[high_field] - prev_c)
    tr3 = abs(prev_c - df[low_field])
    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
    return tr.ewm(span=period, min_periods=period).mean()
