from typing import Dict, Optional, Callable

import numpy as np
import pandas as pd

from api.OandaApi import OandaApi
from config.constants import SMA_L_KEY, SMA_PERIOD_LONG, SMA_PERIOD_SHORT, SMA_S_KEY, ATR_KEY
from core.pair_config import PairConfig
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.open_trade import OpenTrade
from models.position_data import PositionData
from utils.atr import compute_atr
from utils.get_leverage_ratio import get_leverage_ratio
from utils.net_sma_trend import get_net_trend
from utils.no_op import no_op


class BaseAPI:
    INSTRUMENT_API_KEYS = ['name', 'type', 'displayName', 'pipLocation',
                           'displayPrecision', 'tradeUnitsPrecision', 'marginRate',
                           'minimumTrailingStopDistance', 'maximumTrailingStopDistance']

    def __init__(self, oanda_api: OandaApi):
        """
        Initialize the base API client.
        """
        self.oanda_api = oanda_api

    """Base interface for trading platform API clients."""

    def get_all_instruments(self) -> Dict[str, InstrumentData]:
        """
        Get all available trading instruments from Oanda.

        This method fetches the list of available instruments from Oanda API,
        processes the data to extract required fields, and creates InstrumentData objects.
        """
        try:
            instrument_list = self.oanda_api.get_account_instruments()
            if not instrument_list:
                return {}

            instruments: Dict[str, InstrumentData] = {}

            for instrument_data in instrument_list:
                try:
                    # Validate required fields
                    if not all(key in instrument_data for key in self.INSTRUMENT_API_KEYS):
                        raise ValueError(f"Missing required fields in instrument data: {instrument_data}")

                    # Create InstrumentData object
                    instrument = InstrumentData(
                        name=instrument_data['name'],
                        ins_type=instrument_data['type'],
                        displayName=instrument_data['displayName'],
                        pipLocationPrecision=instrument_data['pipLocation'],
                        pipLocation=0,  # Will be set in __post_init__
                        tradeUnitsPrecision=instrument_data['tradeUnitsPrecision'],
                        marginRate=float(instrument_data['marginRate']),
                        displayPrecision=instrument_data['displayPrecision'],
                        minimumTrailingStopDistance=float(instrument_data['minimumTrailingStopDistance']),
                        maximumTrailingStopDistance=float(instrument_data['maximumTrailingStopDistance'])
                    )
                    instruments[instrument.name] = instrument

                except (ValueError, KeyError) as e:
                    # Log error but continue processing other instruments
                    print(f"Error processing instrument data: {e}")
                    continue

            return instruments

        except Exception as e:
            print(f"Error fetching instruments from API: {e}")
            return {}

    def get_trades(self, pair) -> list[OpenTrade] | None:
        trades = self.oanda_api.get_trades_for_instrument(pair)
        if trades is not None and len(trades) > 0:
            return trades
        return None

    def calculate_leverage_ratio(self, pair: str, instrument: InstrumentData, trade_settings: TradeSettings) -> float:
        df_daily: pd.DataFrame = self.oanda_api.get_candles_df(
            pair, completed_only=True, granularity="D", count=500
        )
        return get_leverage_ratio(
            df_daily,
            "D",
            instrument.marginRate,
            trade_settings.vol_target,
            trade_settings.std_lookback,
        )

    def get_position(self, instrument: str) -> Optional[PositionData]:
        """
        Get position information for a specific instrument.
        """
        try:
            position = self.oanda_api.get_instrument_position(instrument)
            if position is None:
                return None

            units, unrealized_pl = position
            return PositionData(
                instrument=instrument,
                units=units,
                unrealized_pl=unrealized_pl,
                margin_used=0.0  # TODO: Calculate margin used
            )
        except Exception as e:
            print(f"Error fetching position for {instrument}: {e}")
            return None

    def place_order(self, pair, use_limit, trade_qty: float, instrument, price, expiry,
                    use_sl=False, stop_loss=None, take_profit=None, logger=no_op, tag=None):
        if use_limit:
            self.oanda_api.place_limit_order(pair, trade_qty, price, expiry, instrument,
                                       logger=logger, use_stop_loss=use_sl, fixed_sl=stop_loss, take_profit=take_profit, tag=tag)
        else:
            self.oanda_api.place_trade(pair, trade_qty, instrument, logger=logger, use_stop_loss=use_sl,
                                        fixed_sl=stop_loss, take_profit=take_profit, tag=tag)


    def calculate_indicators(self, df: pd.DataFrame, pair_config: PairConfig,
                             pair_logger: Callable[[str], None]) -> pd.DataFrame:
        """
        Calculate technical indicators for the given price data.
        """
        # Calculate Simple Moving Averages
        # df[SMA_L_KEY] = df["mid_c"].rolling(window=SMA_PERIOD_LONG).mean()
        # df[SMA_S_KEY] = df["mid_c"].rolling(window=SMA_PERIOD_SHORT).mean()

        # Calculate ATR (Average True Range)
        df[ATR_KEY] = compute_atr(df, period=50)

        # df["net_trend_50"] = get_net_trend(df["mid_c"], 50)
        # df["net_trend_200"] = get_net_trend(df["mid_c"], 200, 10)
        # pair_logger(f"net_trend_50: {np.array(round(df['net_trend_50'].tail(10), 6))}")
        # pair_logger(f"net_trend_200: {np.array(round(df['net_trend_200'].tail(10), 6))}")

        return df