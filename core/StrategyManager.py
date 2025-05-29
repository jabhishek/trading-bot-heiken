import numpy as np
import pandas as pd

from api.OandaApi import OandaApi
from config.constants import HEIKEN_ASHI_STREAK
from models.TradeSettings import TradeSettings
from utils.heiken_ashi import ohlc_to_heiken_ashi


class StrategyManager:
    def __init__(self, api_client: OandaApi, trade_settings: TradeSettings):
        self.api_client = api_client
        self.trade_settings = trade_settings

    def check_for_trigger(self, candles: pd.DataFrame) -> int:
        heikin_ashi: pd.DataFrame = ohlc_to_heiken_ashi(candles)
        last_ha_candle = heikin_ashi.iloc[-1]
        streak: int = last_ha_candle.ha_streak
        is_reversal: bool = np.abs(streak) <= HEIKEN_ASHI_STREAK
        trigger: bool = is_reversal and last_ha_candle.ha_open_at_extreme == 1
        print(f"streak: {streak}, trigger: {trigger}")
        return np.sign(streak) if trigger else 0

    def check_and_place_trade(self):
        pass