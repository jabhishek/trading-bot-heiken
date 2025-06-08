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

    def _check_for_trading_condition(
        self, 
        candles: pd.DataFrame, 
        signal: int, 
        instrument: InstrumentData,
        pair_logger: Callable[[str], None], 
        rejected_logger: Callable[[str], None], 
        pair_config: PairConfig, 
        heikin_ashi: pd.DataFrame, 
        sma_trend_30: int, 
        rsi: float
    ) -> Tuple[int, Optional[float], Optional[float]]:
        sl_price, take_profit, sl_gap = get_probable_stop_loss(
            np.sign(signal), 
            candles,
            instrument.pipLocationPrecision, 
            pair_logger, 
            heikin_ashi
        )

        if signal == 1 and pair_config.short_only:
            rejected_logger(f"short_only: {pair_config.short_only}, skipping trade")
            return 0, None, None
        elif signal == -1 and pair_config.long_only:
            rejected_logger(f"long_only: {pair_config.long_only}, skipping trade")
            return 0, None, None
        elif np.sign(signal) != np.sign(sma_trend_30):
            rejected_logger(f"sma_trend_30: {sma_trend_30} does not match signal: {signal}, skipping trade")
            return 0, None, None
        elif signal > 0 and rsi > 50:
            rejected_logger(f"rsi: {rsi} is too high, skipping trade")
            return 0, None, None
        elif signal < 0 and rsi < 50:
            rejected_logger(f"rsi: {rsi} is too low, skipping trade")
            return 0, None, None
        else:
            return signal, sl_price, take_profit

    def check_and_get_trade_qty(
        self, 
        candles: pd.DataFrame, 
        trigger: int, 
        instrument: InstrumentData,
        pair_logger: Callable[[str], None], 
        rejected_logger: Callable[[str], None], 
        pair_config: PairConfig,
        heikin_ashi: pd.DataFrame, 
        sma_trend_30: int, 
        rsi: float
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        revised_signal, sl_price, take_profit = self._check_for_trading_condition(
            candles, 
            trigger, 
            instrument,
            pair_logger, 
            rejected_logger, 
            pair_config=pair_config,
            heikin_ashi=heikin_ashi, 
            sma_trend_30=sma_trend_30, 
            rsi=rsi
        )
        if revised_signal != 0:
            return True, sl_price, take_profit

        return False, None, None

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