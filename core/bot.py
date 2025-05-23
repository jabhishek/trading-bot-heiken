import time
from typing import Any, List, Optional, Dict, Tuple
import concurrent.futures

import numpy as np
import pandas as pd
from typing_extensions import Callable

from api.OandaApi import OandaApi
from config.constants import SL_PERIOD, ATR_KEY, TP_MULTIPLE
from core.base_api import BaseAPI
from core.candle_manager import CandleManager
from core.log_wrapper import LogManager
from core.pair_config import PairConfig
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.position_data import PositionData
from utils.get_leverage_ratio import get_leverage_ratio
from utils.get_spread_threshold import get_spread_threshold
from utils.get_trade_ex_rate import get_trade_ex_rate
from utils.heiken_ashi import ohlc_to_heiken_ashi
from utils.sma_bands import check_band_position


def get_expiry(granularity: str):
    interval_mapping = {
        "H4": 60 * 4 * 60,
        "H1": 60 * 60,
        "M30": 30 * 60,
        "M15": 15 * 60,
        "M5": 5 * 60,
        "M1": 60,
    }
    return interval_mapping[granularity]


def get_band_scaling_factor(band_position: float) -> float:
    if band_position < 0.5:
        factor = 1
    elif band_position < 0.75:
        factor = 0.5
    elif band_position < 0.8:
        factor = 0.25
    else:
        factor = 0

    return factor


def get_atr_scaling_factor(atr_factor_sl: float) -> float:
    if atr_factor_sl > 8:
        factor = 0.3
    elif atr_factor_sl > 6:
        factor = 0.3
    elif atr_factor_sl > 4.5:
        factor = 0.5
    elif atr_factor_sl > 3:
        factor = 0.75
    else:
        factor = 1

    return factor


def get_probable_stop_loss(direction, df, pipLocationPrecision):
    spread = (df["ask_c"] - df["bid_c"]).iloc[-1]
    price = df["mid_c"].iloc[-1]

    high = df["mid_h"].rolling(window=10).max()
    low = df["mid_l"].rolling(window=10).min()

    if direction > 0:
        sl_price = low.iloc[-1] - spread
    else:
        sl_price = high.iloc[-1] + spread

    sl_price = round(sl_price, abs(pipLocationPrecision))
    sl_gap = round(abs(price - sl_price), abs(pipLocationPrecision))

    take_profit = price + sl_gap * TP_MULTIPLE if direction > 0 else price - sl_gap * TP_MULTIPLE
    take_profit = round(take_profit, abs(pipLocationPrecision))

    return sl_price, take_profit, sl_gap


def check_new_trade_conditions(candles: pd.DataFrame, heikin_ashi: pd.DataFrame, instrument: InstrumentData,
                               atr: float, pair_logger, trade_logger) -> Tuple[bool | None, int | None, float | None, float | None, float]:
    last_ha_candle = heikin_ashi.iloc[-1]
    streak = last_ha_candle.ha_streak
    is_reversal = np.abs(streak) <= 3
    trigger = is_reversal and last_ha_candle.ha_open_at_extreme == 1

    sl_price, take_profit, sl_gap = get_probable_stop_loss(np.sign(streak), candles, instrument.pipLocationPrecision)
    atr_multiplier = sl_gap / atr
    pair_logger(f"ha_open_at_extreme: {last_ha_candle.ha_open_at_extreme}, streak: {last_ha_candle.ha_streak}, atr_multiplier: {atr_multiplier}")
    if trigger:
        if atr_multiplier < 3:
            pair_logger(
                f"==== Heikin buy: streak: {last_ha_candle.ha_streak}, sl_price: {sl_price}, "
                f"take_profit: {take_profit}, sl_gap: {sl_gap}, atr_multiplier: {atr_multiplier} ====")

            return True, np.sign(streak), sl_price, take_profit, atr_multiplier
        else:
            pair_logger(f"atr_multiplier: {atr_multiplier} is too high, skipping trade")

    return False, None, None, None, atr_multiplier


class Bot:
    def __init__(
            self,
            account_settings,
            trade_settings: TradeSettings,
            bot_name: str,
    ) -> None:
        self.api_client: OandaApi = OandaApi(api_key=account_settings.API_KEY, account_id=account_settings.ACCOUNT_ID,
                                             url=account_settings.OANDA_URL)
        self.base_api: BaseAPI = BaseAPI(self.api_client)
        self.trade_settings: TradeSettings = trade_settings
        self.bot_name: str = bot_name

        self.trading_pairs: List[str] = list(trade_settings.pairs)
        self.pair_configs: Dict[str, PairConfig] = {
            pair: PairConfig(pair, settings)
            for pair, settings in trade_settings.pair_settings.items()
        }
        self.polling_period: int = trade_settings.polling_period

        # defaults
        self.sl_period: int = SL_PERIOD

        self.instruments: Dict[str, InstrumentData] = self.base_api.get_all_instruments()
        print(self.instruments)

        # Setup logging
        self.logger: LogManager = LogManager(bot_name, self.trading_pairs)

        # Initialize candle manager with all required parameters
        self.candle_manager: CandleManager = CandleManager(
            pairs=self.trading_pairs,
            api_client=self.api_client,
            pair_settings={pair: config.get_raw_settings() for pair, config in self.pair_configs.items()},
            logger=self.logger
        )

    def setup(self) -> None:
        """Initialize bot components and load required data."""
        try:
            self._load_account_info()
            self.api_client.update_leverage(5)
            self.logger.log_to_main("Bot setup completed successfully")
        except Exception as e:
            self.logger.log_to_error(f"Error during setup: {str(e)}")
            raise

    def _load_account_info(self) -> None:
        """Load and validate account information."""
        try:
            account_info: Dict[str, Any] = self.api_client.get_account_summary()
            if not account_info:
                raise ValueError("Invalid account information received")
            self.logger.log_to_main("Account information loaded successfully")
        except Exception as e:
            self.logger.log_to_error(f"Error loading account info: {str(e)}")
            raise

    def calculate_leverage_ratio(self, pair: str, instrument: InstrumentData) -> float:
        df_daily: pd.DataFrame = self.api_client.get_candles_df(
            pair, completed_only=True, granularity="D", count=500
        )
        return get_leverage_ratio(
            df_daily,
            "D",
            instrument.marginRate,
            self.trade_settings.vol_target,
            self.trade_settings.std_lookback,
        )

    def process_pair(self, pair: str) -> None:
        """Process a single trading pair."""
        try:
            # Get pair config
            pair_config: PairConfig = self.pair_configs[pair]

            pair_logger: Callable[[str], None] = self.logger.log_message_builder(pair)
            trade_logger: Callable[[str], None] = self.logger.log_trade_builder(pair, pair_config.granularity)
            rejected_logger: Callable[[str], None] = self.logger.log_rejected_builder(pair, pair_config.granularity)
            instrument = self.instruments[pair]

            # Get account value and exposure metrics
            account_info: Dict[str, Any] = self.api_client.get_account_summary()
            nav: float = float(account_info["NAV"])

            # Get current position
            position_data_1: Optional[PositionData] = self.base_api.get_position(pair)
            current_units = position_data_1.units if position_data_1 else 0
            pl = position_data_1.unrealized_pl if position_data_1 else 0
            pair_logger(
                f"********* {pair_config.granularity} units: {current_units:.2f}, pl: {pl:.2f} *********")

            # Get latest candles
            candles: Optional[pd.DataFrame] = self.api_client.get_candles_df(
                pair,
                completed_only=True,
                granularity=pair_config.granularity,
                count=5000
            )

            if candles is None or candles.empty:
                self.logger.log_to_error(f"No candles found for {pair}")
                return

            # Calculate indicators
            candles = self.base_api.calculate_indicators(candles, pair_config, pair_logger)

            heikin_ashi: pd.DataFrame = ohlc_to_heiken_ashi(candles)

            # Get current price
            current_price: float = candles.iloc[-1]["mid_c"]
            atr = candles.iloc[-1][ATR_KEY]

            # get upper and lower price bands
            band_position_200 = check_band_position(candles, current_price, sma_period=200)
            band_position_50 = check_band_position(candles, current_price, sma_period=50)
            pair_logger(f"price within band for periods - 200: {band_position_200:.2f}, 50: {band_position_50:.2f}")

            # Calculate position size based on NAV and pair weight
            exposure_at_no_leverage: float = nav * pair_config.weight

            # Calculate exposure metrics
            leverage_ratio: float = self.calculate_leverage_ratio(pair, instrument)
            max_gbp_exposure: float = leverage_ratio * exposure_at_no_leverage
            ex_rate: float = get_trade_ex_rate(pair, self.api_client)
            max_currency_exposure: float = max_gbp_exposure * ex_rate
            pair_logger(
                f"leverage_ratio: {leverage_ratio}, max_gbp_exposure: {max_gbp_exposure:.2f}, ex_rate: {ex_rate:.5f}, max_currency_exposure: {max_currency_exposure:.2f}")

            base_qty = (max_currency_exposure / current_price) * 1
            current_utilisation = current_units / base_qty

            pair_logger(
                f"current_utilisation: {round(current_utilisation, 2)}, base_qty:{round(base_qty, 2)}")

            # get spread
            current_spread, spread_threshold, current_price = get_spread_threshold(pair, candles, self.api_client,
                                                                                   pair_logger)
            is_acceptable_spread = current_spread <= spread_threshold
            use_limit_order = not is_acceptable_spread
            pair_logger(f"is_acceptable_spread: {is_acceptable_spread}, use_limit_order: {use_limit_order}")

            if current_units == 0:
                should_trade, direction, sl_price, take_profit, atr_multiplier = check_new_trade_conditions(candles, heikin_ashi, instrument, atr, pair_logger, trade_logger)
                if should_trade:
                    qty = base_qty if direction > 0 else -base_qty
                    trade_logger(f"Placing trade: qty: {qty}, sl_price: {sl_price}, take_profit: {take_profit}, atr_multiplier: {atr_multiplier}")
                    self.api_client.place_trade(pair, qty, instrument, logger=self.logger.log_message,
                                         trailing_stop_gap=None, use_stop_loss=True,
                                         take_profit=take_profit,
                                         fixed_sl=sl_price)


        except Exception as e:
            self.logger.log_to_error(f"Error processing {pair}: {str(e)}")
            raise

    def process_pairs(self, pairs: List[str]) -> None:
        """Process multiple pairs in parallel."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures: List[concurrent.futures.Future] = [executor.submit(self.process_pair, pair) for pair in pairs]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.log_to_error(f"Error in parallel processing: {str(e)}")

    def run(self) -> None:
        """Run the main bot loop."""

        try:
            self.setup()
            self.logger.log_to_main("Starting main loop")
            # self.process_pairs(self.trading_pairs)

            while True:
                try:
                    tm_mday = time.localtime().tm_mday
                    tm_hour = time.localtime().tm_hour
                    tm_min = time.localtime().tm_min
                    tm_sec = time.localtime().tm_sec

                    if tm_sec < 30 and tm_sec % 5 < 3:
                        print(f"{tm_mday} {tm_hour}:{tm_min}:{tm_sec}")
                        # Check for new candles
                        pairs_with_new_candles: List[str] = self.candle_manager.update_timings()

                        if pairs_with_new_candles:
                            self.logger.log_to_main(f"Processing pairs with new candles: {pairs_with_new_candles}")
                            self.process_pairs(pairs_with_new_candles)

                    time.sleep(self.polling_period)

                except Exception as e:
                    self.logger.log_to_error(f"Error in main loop: {str(e)}")
                    time.sleep(self.polling_period)

        except Exception as e:
            self.logger.log_to_error(f"Fatal error: {str(e)}")
            raise

