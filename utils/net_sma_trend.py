import numpy as np
import pandas as pd


def get_trend(series: pd.Series, horizon):
    df = pd.DataFrame(index=series.index)
    df["sma"] = series.rolling(window=horizon, min_periods=horizon).mean()
    df["diff"] = df["sma"].diff()
    df["trend"] = np.where(df['diff'] > 0, 1,
                                        np.where(df['diff'] < 0, -1, 0))
    df["trend"] = df["trend"].ffill()
    return np.sign(df["diff"])

def get_net_trend(series: pd.Series, horizon, offset=5):
    df = pd.DataFrame(index=series.index)
    for period in np.arange(horizon - offset, horizon + 2, 1):
        df[f"trend_{period}"] = get_trend(series, period)
        # df += get_trend(series, period)

    df["trend"] = df.mean(axis=1)
    # set all the values inside column "trend" equal to 0 if the existing value is neither 1 or -1
    df.loc[~df['trend'].isin([1, -1]), 'trend'] = 0
    # df['trend'] = df['trend'].replace(to_replace=0,value=np.nan).ffill()
    return df["trend"]
