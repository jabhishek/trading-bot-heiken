import pandas as pd

from utils.get_std_dev import get_std_dev


def get_leverage_ratio(df: pd.DataFrame, granularity: str, marginRate: float, vol_target,
                       std_lookback, max_lev_ratio: float = 10.0) -> float:
    def_lev_ratio = round(1 / marginRate, 2)
    st_dev = get_std_dev(df, granularity, std_lookback=std_lookback)

    if vol_target is None:
        return min(def_lev_ratio, max_lev_ratio)

    # Calculate leverage ratio capped by max_lev_ratio
    return min(round(vol_target / st_dev, 3), max_lev_ratio)