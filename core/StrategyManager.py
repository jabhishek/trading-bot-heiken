from typing import Tuple, Callable, Optional

import numpy as np
import pandas as pd

from api.OandaApi import OandaApi
from config.constants import HEIKEN_ASHI_STREAK, ATR_KEY, ATR_RISK_FILTER
from core.base_api import BaseAPI
from core.pair_config import PairConfig
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.open_trade import OpenTrade
from utils.stop_loss import get_probable_stop_loss


class StrategyManager:
    def __init__(self, api_client: OandaApi, trade_settings: TradeSettings, base_api: BaseAPI) -> None:
        self.api_client = api_client
        self.trade_settings = trade_settings
        self.base_api = base_api

    def check_for_trigger(self, heikin_ashi: pd.DataFrame, logger: Callable[[str], None]) -> int:
        last_ha_candle = heikin_ashi.iloc[-1]
        streak: int = last_ha_candle.ha_streak
        trigger: bool = np.abs(streak) <= HEIKEN_ASHI_STREAK and last_ha_candle.ha_open_at_extreme == 1
        logger(f"streak: {streak}, trigger: {trigger}")
        return np.sign(streak) if trigger else 0
        # return np.sign(streak)

    def _check_for_trading_condition(
            self,
            signal: int,
            rejected_logger: Callable[[str], None],
            pair_config: PairConfig,
            sma_trend_30: int,
            rsi: float, net_strength: float
    ) -> int:
        if signal == 1 and pair_config.short_only:
            rejected_logger(f"short_only: {pair_config.short_only}, skipping trade")
            return 0
        elif signal == -1 and pair_config.long_only:
            rejected_logger(f"long_only: {pair_config.long_only}, skipping trade")
            return 0
        elif np.sign(signal) != np.sign(net_strength):
            rejected_logger(f"net_strength: {round(net_strength, 2)} does not match signal: {signal}, skipping trade")
            return 0
        # elif np.sign(signal) != np.sign(sma_trend_30):
        #     rejected_logger(f"sma_trend_30: {sma_trend_30} does not match signal: {signal}, skipping trade")
        #     return 0
        elif signal > 0 and rsi > 70:
            rejected_logger(f"rsi: {rsi} is too high, skipping trade")
            return 0
        elif signal < 0 and rsi < 30:
            rejected_logger(f"rsi: {rsi} is too low, skipping trade")
            return 0
        else:
            return signal

    def check_and_get_trade_qty(
            self,
            trigger: int,
            rejected_logger: Callable[[str], None],
            pair_config: PairConfig,
            sma_trend_30: int,
            rsi: float,
            net_strength: float
    ) -> bool:
        revised_signal = self._check_for_trading_condition(
            trigger,
            rejected_logger,
            pair_config=pair_config,
            sma_trend_30=sma_trend_30,
            rsi=rsi,
            net_strength=net_strength
        )
        return revised_signal != 0

    def check_for_closing_trade(
            self,
            t: OpenTrade,
            ex_rate: float,
            atr: float,
            trigger: int,
            pair_logger: Callable[[str], None]
    ) -> float:
        trade_pl = t.unrealizedPL
        pl_multiple = np.abs(round(t.unrealizedPL * ex_rate / (t.currentUnits * atr), 2))

        if trigger != 0 and np.sign(trigger) != np.sign(t.currentUnits):
            pair_logger(
                f"check for booking profit. Trigger: {trigger}, trade_pl: {trade_pl:.2f}, pl_multiple: {pl_multiple:.2f}")
            if trade_pl > 0 and pl_multiple > 2:
                return -1 * t.currentUnits / 2

        return 0
