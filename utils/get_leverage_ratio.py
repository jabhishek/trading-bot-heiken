import pandas as pd
from typing import Optional

from utils.get_std_dev import get_std_dev


def get_leverage_ratio(df: pd.DataFrame, granularity: str, marginRate: float, vol_target: Optional[float],
                       std_lookback: int, max_lev_ratio: float = 10.0) -> float:
    """
    Calculate the leverage ratio based on volatility target and market conditions.
    
    Args:
        df (pd.DataFrame): Price data DataFrame
        granularity (str): Timeframe granularity
        marginRate (float): Broker's margin rate
        vol_target (Optional[float]): Target volatility
        std_lookback (int): Lookback period for standard deviation calculation
        max_lev_ratio (float): Maximum allowed leverage ratio
        
    Returns:
        float: Calculated leverage ratio
    """
    def_lev_ratio = round(1 / marginRate, 2)
    st_dev = get_std_dev(df, granularity, std_lookback=std_lookback)

    if vol_target is None:
        return min(def_lev_ratio, max_lev_ratio)

    # Calculate leverage ratio capped by max_lev_ratio
    return min(round(vol_target / st_dev, 3), max_lev_ratio)