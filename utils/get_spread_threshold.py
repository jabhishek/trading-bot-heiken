import pandas as pd
from typing import Tuple

from api.OandaApi import OandaApi
from models.api_price import ApiPrice


def get_spread_threshold(pair: str, df: pd.DataFrame, api: OandaApi, logger: Callable[[str], None]) -> Tuple[float, float, float]:
    spread_series = df["ask_c"] - df["bid_c"]
    spread_series.dropna(inplace=True)

    current_price: ApiPrice = api.get_price(pair)
    desc = spread_series.describe(percentiles=[0.05, 0.25, 0.5, 0.75])

    # desc_dict = desc.to_dict()
    # desc_str = ", ".join(
    #     f"{key}={round(value, 5)}"
    #     for key, value in desc_dict.items()
    #     if "%" in key
    # )
    # logger(f"spread distribution: {desc_str}")

    spread_threshold = float(desc["50%"].round(5))
    current_spread = round(current_price.ask - current_price.bid, 5)

    return current_spread, spread_threshold, current_price.price