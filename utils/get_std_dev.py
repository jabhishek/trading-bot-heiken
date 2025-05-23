import numpy as np
import pandas as pd

from config.constants import PERIODS_IN_YEAR


def get_std_dev(df, granularity: str, std_lookback) -> float:
    df["diff"] = df["mid_c"].pct_change()
    st_dev_series: pd.Series = df["diff"].ewm(span=std_lookback).std() * np.sqrt(PERIODS_IN_YEAR[granularity])
    # smooth the series
    st_dev_series = st_dev_series.ewm(span=3).mean()

    return st_dev_series.iloc[-1]