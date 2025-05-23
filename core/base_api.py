from typing import Dict, Optional, Callable

import numpy as np
import pandas as pd

from api.OandaApi import OandaApi
from config.constants import SMA_L_KEY, SMA_PERIOD_LONG, SMA_PERIOD_SHORT, SMA_S_KEY, ATR_KEY
from core.pair_config import PairConfig
from models.instrument_data import InstrumentData
from models.open_trade import OpenTrade
from models.position_data import PositionData
from utils.atr import compute_atr
from utils.net_sma_trend import get_net_trend


class BaseAPI:
    INSTRUMENT_API_KEYS = ['name', 'type', 'displayName', 'pipLocation',
                           'displayPrecision', 'tradeUnitsPrecision', 'marginRate',
                           'minimumTrailingStopDistance', 'maximumTrailingStopDistance']

    def __init__(self, oanda_api: OandaApi):
        """
        Initialize the base API client.

        Args:
            oanda_api (OandaApi): Instance of OandaApi for making API calls

        The initialization process:
        1. Sets up API client
        2. Validates connection
        3. Prepares for data processing

        Raises:
            APIError: If API connection fails
            ValueError: If API client is invalid
        """
        self.oanda_api = oanda_api

    """Base interface for trading platform API clients."""

    def get_all_instruments(self) -> Dict[str, InstrumentData]:
        """
        Get all available trading instruments from Oanda.

        This method fetches the list of available instruments from Oanda API,
        processes the data to extract required fields, and creates InstrumentData objects.

        Returns:
            Dictionary mapping instrument names to InstrumentData objects.
            Returns an empty dictionary if the API call fails or no instruments are found.

        Raises:
            ValueError: If the API response is invalid or missing required fields
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

    def get_position(self, instrument: str) -> Optional[PositionData]:
        """
        Get position information for a specific instrument.

        Args:
            instrument: Name of the instrument to get position for

        Returns:
            PositionData object if position exists, None otherwise
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

    def calculate_indicators(self, df: pd.DataFrame, pair_config: PairConfig,
                             pair_logger: Callable[[str], None]) -> pd.DataFrame:
        """
        Calculate technical indicators for the given price data.

        Args:
            df: DataFrame containing price data with columns:
                - time: datetime index
                - mid_o: open price
                - mid_h: high price
                - mid_l: low price
                - mid_c: close price

        Returns:
            DataFrame with additional indicator columns
        """
        # Calculate Simple Moving Averages
        df[SMA_L_KEY] = df["mid_c"].rolling(window=SMA_PERIOD_LONG).mean()
        df[SMA_S_KEY] = df["mid_c"].rolling(window=SMA_PERIOD_SHORT).mean()

        # Calculate ATR (Average True Range)
        df[ATR_KEY] = compute_atr(df, period=50)

        df["net_trend_50"] = get_net_trend(df["mid_c"], 50)
        df["net_trend_200"] = get_net_trend(df["mid_c"], 200, 10)
        pair_logger(f"net_trend_50: {np.array(round(df['net_trend_50'].tail(10), 6))}")
        pair_logger(f"net_trend_200: {np.array(round(df['net_trend_200'].tail(10), 6))}")

        return df