from typing import Tuple

import numpy as np
import pandas as pd

from api.OandaApi import OandaApi
from config.constants import HEIKEN_ASHI_STREAK, ATR_KEY, ATR_RISK_FILTER
from core.base_api import BaseAPI
from core.pair_config import PairConfig
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from utils.heiken_ashi import ohlc_to_heiken_ashi
from utils.stop_loss import get_probable_stop_loss


class StrategyManager:
    def __init__(self, api_client: OandaApi, trade_settings: TradeSettings, base_api: BaseAPI) -> None:
        self.api_client = api_client
        self.trade_settings = trade_settings
        self.base_api = base_api

    def check_for_trigger(self, candles: pd.DataFrame, logger) -> int:
        heikin_ashi: pd.DataFrame = ohlc_to_heiken_ashi(candles)
        last_ha_candle = heikin_ashi.iloc[-1]
        streak: int = last_ha_candle.ha_streak
        trigger: bool = np.abs(streak) <= HEIKEN_ASHI_STREAK and last_ha_candle.ha_open_at_extreme == 1
        logger(f"streak: {streak}, trigger: {trigger}")
        return np.sign(streak) if trigger else 0

    def _check_for_trading_condition(self, candles: pd.DataFrame, signal: int, instrument: InstrumentData,
                        pair_logger, rejected_logger, trend_strength, pair_config) -> Tuple[int, float | None, float | None]:
        atr = candles.iloc[-1][ATR_KEY]
        sl_price, take_profit, sl_gap = get_probable_stop_loss(np.sign(signal), candles,
                                                               instrument.pipLocationPrecision)
        atr_multiplier = sl_gap / atr
        if signal == 1 and pair_config.short_only:
            rejected_logger(f"short_only: {pair_config.short_only}, skipping trade")
            return 0, None, None
        elif signal == -1 and pair_config.long_only:
            rejected_logger(f"long_only: {pair_config.long_only}, skipping trade")
            return 0, None, None
        elif atr_multiplier > ATR_RISK_FILTER:
            rejected_logger(f"atr_multiplier: {atr_multiplier} is too high, skipping trade")
            return 0, None, None
        elif np.sign(signal) != np.sign(trend_strength):
            rejected_logger(f"trend_strength: {round(trend_strength, 2)} does not match signal: {signal}, skipping trade")
            return 0, None, None
        else:
            return signal, sl_price, take_profit

    def check_and_get_trade_qty(self, candles: pd.DataFrame, trigger: int, instrument: InstrumentData,
                                qty_at_net_strength: float, pair_logger, rejected_logger, trend_strength: float, pair_config: PairConfig):
        revised_signal, sl_price, take_profit = self._check_for_trading_condition(candles, trigger, instrument,
                                                                                  pair_logger, rejected_logger,
                                                                                  trend_strength=trend_strength, pair_config=pair_config)
        if revised_signal != 0:
            return qty_at_net_strength, sl_price, take_profit

        return 0, None, None