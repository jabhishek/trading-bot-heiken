import time
from typing import Any, List, Optional, Dict
import concurrent.futures

import numpy as np
import pandas as pd
from typing_extensions import Callable

from api.OandaApi import OandaApi
from core.StrategyManager import StrategyManager
from core.base_api import BaseAPI
from core.candle_manager import CandleManager
from core.log_wrapper import LogManager
from core.pair_config import PairConfig
from indicators.rsi import get_rsi
from indicators.trix import calculate_trix, convert_series_to_signals
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.position_data import PositionData
from utils.get_expiry import get_expiry
from utils.get_spread_threshold import get_spread_threshold
from utils.get_trade_ex_rate import get_trade_ex_rate
from utils.heiken_ashi import ohlc_to_heiken_ashi
from utils.net_sma_trend import get_net_trend
from utils.net_strength import compute_strength

HIGHER_GRAN_MAPPING = {
    "M5": "H1",
    "M15": "H4",
    "H1": "H4",
    "H4": "D",
}

def get_additional_qty(ideal_qty: float, current_position: float) -> float:
    if np.sign(ideal_qty) != np.sign(current_position):
        return 0

    diff = ideal_qty - current_position
    if np.sign(diff) != np.sign(current_position):
        return 0

    return diff

def get_reduce_qty(ideal_qty: float, current_position: float, pair_logger) -> float:
    diff = ideal_qty - current_position
    if np.sign(diff) == np.sign(current_position):
        pair_logger(f"diff: {diff} has same sign as current_position: {current_position}, not reducing")
        return 0

    return diff


def get_trade_qty(base_qty, spare_qty, pair_logger) -> float:
    max_qty = base_qty * 0.5
    pair_logger(f"max_qty: {round(max_qty, 2)}, spare_qty: {round(spare_qty, 2)}")
    additional_qty = np.sign(spare_qty) * min(abs(spare_qty), max_qty)
    return additional_qty


def get_ideal_qty(base_qty, net_strength) -> float:
    return base_qty * net_strength


def get_net_strength(candles, pair_logger):

    candles = get_net_strength_series(candles, pair_logger)

    bullish_strength = candles['bullish_strength_s'].iloc[-1]
    bearish_strength = candles['bearish_strength_s'].iloc[-1]
    net_strength = bullish_strength - bearish_strength

    return net_strength


def get_net_strength_series(candles, pair_logger):
    candles["trix_9"] = calculate_trix(candles["mid_c"], 9)
    candles["trix_9"] = convert_series_to_signals(candles["trix_9"])
    candles["trix_15"] = calculate_trix(candles["mid_c"], 15)
    candles["trix_15"] = convert_series_to_signals(candles["trix_15"])
    pair_logger(f"trix_9: {np.array(candles['trix_9'].tail(10))}")
    pair_logger(f"trix_15: {np.array(candles['trix_15'].tail(10))}")
    candles["sma_200"] = candles["mid_c"].rolling(window=200).mean()
    candles["sma_100"] = candles["mid_c"].rolling(window=100).mean()
    candles["sma_50"] = candles["mid_c"].rolling(window=50).mean()
    candles["sma_30"] = candles["mid_c"].rolling(window=30).mean()
    candles["sma_10"] = candles["mid_c"].rolling(window=10).mean()
    candles["net_trend_200"] = get_net_trend(candles["mid_c"], 200)
    candles["net_trend_100"] = get_net_trend(candles["mid_c"], 100)
    candles["net_trend_50"] = get_net_trend(candles["mid_c"], 50)
    candles["net_trend_30"] = get_net_trend(candles["mid_c"], 30)
    # net_trend_30: int = candles["net_trend_30"].iloc[-1]
    candles[['bearish_strength', 'bullish_strength']] = candles.apply(compute_strength, axis=1)
    candles['bearish_strength_s'] = candles['bearish_strength'].ewm(span=10, adjust=False).mean()
    candles['bullish_strength_s'] = candles['bullish_strength'].ewm(span=10, adjust=False).mean()
    candles['net_strength'] = candles['bullish_strength'] - candles['bearish_strength']
    candles['net_strength_s'] = candles['bullish_strength_s'] - candles['bearish_strength_s']
    candles['net_strength_s'] = round(candles['net_strength_s'], 2)
    pair_logger(f"net_strength: {np.array(round(candles['net_strength'].tail(10), 2))}")
    pair_logger(f"net_strength smoothed: {np.array(candles['net_strength_s'].tail(10))}")

    return candles.copy()


class Bot:
    def __init__(
            self,
            trade_settings: TradeSettings,
            bot_name: str,
            api_client: OandaApi,
            strategy_manager: StrategyManager,
            base_api: BaseAPI
    ) -> None:
        self.api_client = api_client
        self.base_api: BaseAPI = BaseAPI(self.api_client)
        self.trade_settings: TradeSettings = trade_settings
        self.bot_name: str = bot_name
        self.strategy_manager: StrategyManager = strategy_manager

        self.trading_pairs: List[str] = list(trade_settings.pairs)
        self.pair_configs: Dict[str, PairConfig] = {
            pair: PairConfig(pair, settings)
            for pair, settings in trade_settings.pair_settings.items()
        }
        self.polling_period: int = trade_settings.polling_period

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
        self.setup()

    def setup(self) -> None:
        """Initialize bot components and load required data."""
        try:
            self.api_client.update_leverage(5)
            self.logger.log_to_main("Bot setup completed successfully")
        except Exception as e:
            self.logger.log_to_error(f"Error during setup: {str(e)}")
            raise

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
            position_data: Optional[PositionData] = self.base_api.get_position(pair)
            current_units: float = position_data.units if position_data else 0.0
            pl = position_data.unrealized_pl if position_data else 0
            ex_rate: float = get_trade_ex_rate(pair, self.api_client)

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

            last_candle = candles.iloc[-1]
            pair_logger(
                f"********* {pair_config.granularity} {last_candle["time"]}, config: {pair_config} *********")

            rsi = get_rsi(candles["mid_c"], 14)
            pair_logger(f"rsi: {rsi:.2f}")

            # Calculate indicators
            candles = self.base_api.calculate_indicators(candles, pair_config, pair_logger)

            # higher granularity trend
            higher_granularity: str = HIGHER_GRAN_MAPPING.get(pair_config.granularity, pair_config.granularity)
            higher_candles: Optional[pd.DataFrame] = self.api_client.get_candles_df(
                pair,
                completed_only=True,
                granularity=higher_granularity,
                count=5000
            )
            if higher_candles is None or higher_candles.empty:
                self.logger.log_to_error(f"No higher granularity candles found for {pair} with granularity {higher_granularity}")
                return

            pair_logger(f"Higher granularity: {higher_granularity}")
            higher_net_strength = get_net_strength(higher_candles, pair_logger)
            pair_logger(f"Higher net_strength: {round(higher_net_strength, 2)}")

            net_strength = get_net_strength(candles, pair_logger)
            pair_logger(f"net_strength: {round(net_strength, 2)}")

            # Get current price
            last_close: float = candles.iloc[-1]["mid_c"]

            # Calculate position size based on NAV and pair weight
            exposure_at_no_leverage: float = nav * pair_config.weight

            # Calculate exposure metrics
            base_qty, min_qty, qty_to_sell, spare_qty = self.get_quantities(current_units, ex_rate,
                                                                                       exposure_at_no_leverage,
                                                                                       instrument, last_close,
                                                                                       net_strength, pair, pair_logger)

            # get spread
            current_spread, spread_threshold, bid, ask, mid = get_spread_threshold(pair, candles, self.api_client,
                                                                                pair_logger)
            bid_price = round(bid, abs(instrument.pipLocationPrecision))
            ask_price = round(ask, abs(instrument.pipLocationPrecision))
            mid_price = round(mid, abs(instrument.pipLocationPrecision))
            pair_logger(f"bid_price: {bid_price:.5f}, ask_price: {ask_price}, last_close: {last_close:.5f}")

            is_acceptable_spread = current_spread <= spread_threshold

            heikin_ashi: pd.DataFrame = ohlc_to_heiken_ashi(candles.iloc[-100:].copy())

            trigger = self.strategy_manager.check_for_trigger(heikin_ashi, pair_logger)
            pair_logger(
                f"trigger: {trigger}, current_units: {np.round(current_units, 2)}")

            tag = f"strength_{net_strength},rsi:{rsi:.2f}"

            if spare_qty != 0:
                can_trade = self.check_can_trade(current_units, net_strength, pair_config, rejected_logger, rsi,
                                                 trigger)

                if can_trade:
                    trade_qty = get_trade_qty(base_qty, spare_qty, pair_logger)

                    if trade_qty != 0:
                        less_than_min = abs(spare_qty) < min_qty
                        use_limit_order = not is_acceptable_spread or less_than_min

                        limit_price = bid_price if trade_qty > 0 else ask_price

                        trade_logger(
                            f"Placed {"new" if current_units == 0 else "additional"} trade: qty: {round(trade_qty, 2)}, limit_price: {limit_price}, net_strength: {round(net_strength, 2)}, rsi: {rsi:.2f}, min_qty: {min_qty}, use_limit_order: {use_limit_order}")
                        self.base_api.place_order(pair, use_limit_order, trade_qty, instrument, limit_price,
                                                  get_expiry(pair_config.granularity), use_sl=True,
                                                  stop_loss=None, take_profit=None,
                                                  logger=self.logger.log_message, tag=tag)
                else:
                    pair_logger(
                        f"Trade not initiated - can_trade: {can_trade}, trigger: {trigger}, net_strength: {net_strength}, rsi: {rsi:.2f}")

            if qty_to_sell != 0:
                limit_price = mid_price
                last_ha_candle = heikin_ashi.iloc[-1]
                streak: int = last_ha_candle.ha_streak
                should_check_for_reduce = np.sign(streak) != np.sign(current_units)
                # pair_logger(
                #     f"should_check_for_reduce: {should_check_for_reduce}, current_units: {current_units}, trigger: {trigger}, streak: {streak}")

                if should_check_for_reduce:
                    self.check_for_reduce(current_units, instrument, is_acceptable_spread, limit_price,
                                          min_qty, pair, pair_config, pair_logger, trade_logger,
                                          trigger, tag=tag, qty_to_sell=qty_to_sell, net_strength=net_strength)

        except Exception as e:
            self.logger.log_to_error(f"Error processing {pair}: {str(e)}")
            print(e)
            raise

    def get_quantities(self, current_units, ex_rate, exposure_at_no_leverage, instrument, last_close, net_strength,
                       pair, pair_logger):
        leverage_ratio: float = self.base_api.calculate_leverage_ratio(pair, instrument, self.trade_settings)
        max_gbp_exposure: float = leverage_ratio * exposure_at_no_leverage
        max_currency_exposure: float = max_gbp_exposure * ex_rate
        pair_logger(
            f"leverage_ratio: {leverage_ratio}, max_gbp_exposure: {max_gbp_exposure:.2f}, ex_rate: {ex_rate:.5f}, max_currency_exposure: {max_currency_exposure:.2f}")
        base_qty = (max_currency_exposure / last_close) * 1
        min_qty = 0.15 * base_qty
        ideal_qty: float = get_ideal_qty(base_qty, net_strength)
        spare_qty: float = ideal_qty if current_units == 0 else get_additional_qty(ideal_qty, current_units)
        qty_to_sell = 0 if current_units == 0 else get_reduce_qty(ideal_qty, current_units, pair_logger)
        pair_logger(f"spare_qty: {round(spare_qty, 2)}, qty_to_sell: {round(qty_to_sell, 2)}")
        return base_qty, min_qty, qty_to_sell, spare_qty

    def check_can_trade(self, current_units, net_strength, pair_config, rejected_logger, rsi, trigger):
        if current_units == 0 and abs(net_strength) > 0.5:
            rejected_logger(
                f"net_strength: {round(net_strength, 2)} is too high, not initiating trade. trigger: {trigger}")
            return False

        if current_units != 0 and np.sign(trigger) != np.sign(current_units):
            rejected_logger(
                f"trigger: {trigger} does not match current_units: {current_units}, not adding to trade")
            return False

        return self.strategy_manager.check_and_get_trade_qty(trigger=trigger,
                                                                  rejected_logger=rejected_logger,
                                                                  pair_config=pair_config,
                                                                  rsi=rsi,
                                                                  net_strength=net_strength)


    def check_for_reduce(self, current_units, instrument, is_acceptable_spread, limit_price, min_qty, pair,
                         pair_config, pair_logger, trade_logger, trigger, tag: str, qty_to_sell: float, net_strength: float) -> None:
        less_than_min = abs(qty_to_sell) < min_qty
        use_limit_order = not is_acceptable_spread or less_than_min
        if qty_to_sell != 0:
            trade_logger(
                f"reducing position - net_strength: {round(net_strength, 2)}, limit_price: {limit_price}, qty_to_sell: {round(qty_to_sell, 2)}, current_units: {current_units:.2f}, use_limit_order: {use_limit_order}, min_qty: {min_qty}")
            self.base_api.place_order(pair, use_limit_order, qty_to_sell, instrument, limit_price,
                                      get_expiry(pair_config.granularity),
                                      logger=self.logger.log_message, tag=tag)
        else:
            pair_logger(
                f"qty_to_sell is 0, not placing reduce trade. current_units: {round(current_units, 2)}, trigger: {trigger}")
            pass

    def process_pairs(self, pairs: List[str]) -> None:
        """Process multiple pairs in parallel."""
        # for p in pairs:
        #     self.logger.log_to_main(f"Processing pair: {p}")
        #     self.process_pair(pair=p)

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
            self.logger.log_to_main("Starting main loop")
            self.process_pairs(self.trading_pairs)

            while True:
                try:
                    tm_mday = time.localtime().tm_mday
                    tm_hour = time.localtime().tm_hour
                    tm_min = time.localtime().tm_min
                    tm_sec = time.localtime().tm_sec

                    if tm_sec % 5 < 2 and tm_min % 5 < 2:
                        print(f"---- {tm_mday} {tm_hour}:{tm_min}:{tm_sec} - {tm_min % 5} - updating timings")
                        pairs_with_new_candles: List[str] = self.candle_manager.update_timings()

                        if pairs_with_new_candles:
                            self.logger.log_to_main(f"Processing pairs with new candles: {pairs_with_new_candles}")
                            self.process_pairs(pairs_with_new_candles)
                    # elif tm_min % 5 == 2 and tm_sec == 30:
                    #     print(f"---- {tm_mday} {tm_hour}:{tm_min}:{tm_sec} - {tm_min % 5} - processing all pairs")
                    #     self.process_pairs(self.trading_pairs)
                    #     pass
                    else:
                        print(f"---- {tm_mday} {tm_hour}:{tm_min}:{tm_sec} - {tm_min % 5}")
                    time.sleep(self.polling_period)

                except Exception as e:
                    self.logger.log_to_error(f"Error in main loop: {str(e)}")
                    time.sleep(self.polling_period)

        except Exception as e:
            self.logger.log_to_error(f"Fatal error: {str(e)}")
            raise
