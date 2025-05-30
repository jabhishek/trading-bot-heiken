import time
from typing import Any, List, Optional, Dict, Tuple
import concurrent.futures

import numpy as np
import pandas as pd
from typing_extensions import Callable

from api.OandaApi import OandaApi
from config.constants import ATR_KEY, HEIKEN_ASHI_STREAK, ATR_RISK_FILTER, SMA_PERIOD_LONG, \
    SMA_PERIOD_SHORT
from core.StrategyManager import StrategyManager
from core.base_api import BaseAPI
from core.candle_manager import CandleManager
from core.log_wrapper import LogManager
from core.pair_config import PairConfig
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.position_data import PositionData
from utils.get_expiry import get_expiry
from utils.get_spread_threshold import get_spread_threshold
from utils.get_trade_ex_rate import get_trade_ex_rate
from utils.net_strength import get_net_bullish_strength
from utils.no_op import no_op
from utils.sma_bands import check_band_position

def get_additional_qty(ideal_qty, current_position):
    if np.sign(ideal_qty) != np.sign(current_position):
        return 0

    diff = ideal_qty - current_position
    if np.sign(diff) != np.sign(current_position):
        return 0

    return diff

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
            current_units = position_data.units if position_data else 0
            pl = position_data.unrealized_pl if position_data else 0
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

            # Get current price
            current_price: float = candles.iloc[-1]["mid_c"]

            # get upper and lower price bands
            band_position_200 = check_band_position(candles, current_price, sma_period=SMA_PERIOD_LONG, logger=pair_logger)
            band_position_50 = check_band_position(candles, current_price, sma_period=SMA_PERIOD_SHORT, logger=pair_logger)
            pair_logger(f"price within band for periods - 200: {band_position_200:.2f}, 50: {band_position_50:.2f}")
            # Calculate position size based on NAV and pair weight
            exposure_at_no_leverage: float = nav * pair_config.weight

            # Calculate exposure metrics
            leverage_ratio: float = self.base_api.calculate_leverage_ratio(pair, instrument, self.trade_settings)
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

            net_strength = get_net_bullish_strength(candles["mid_c"], logger=pair_logger, steps_logger=no_op)
            qty_at_net_strength = base_qty * net_strength
            pair_logger(f"net_strength: {round(net_strength, 2)}, qty_at_net_strength: {round(qty_at_net_strength, 2)}")

            trigger = self.strategy_manager.check_for_trigger(candles, pair_logger)

            # look for new positions
            if current_units == 0 and trigger != 0:
                pair_logger(f"checking for trade - trigger: {trigger}")
                qty, sl_price, take_profit = self.strategy_manager.check_and_get_trade_qty(candles=candles, trigger=trigger, instrument=instrument,
                                                                                           qty=qty_at_net_strength, pair_logger=pair_logger,
                                                                                           rejected_logger=rejected_logger, trend_strength=net_strength,
                                                                                           pair_config=pair_config)
                if qty != 0:
                    trade_logger(f"Placed trade: qty: {qty}, trend_strength: {net_strength}")
                    self.base_api.place_order(pair, use_limit_order, qty, instrument, current_price,
                                              get_expiry(pair_config.granularity), use_sl=True,
                                              stop_loss=sl_price, take_profit=take_profit, logger=self.logger.log_message)
            elif current_units != 0:
                # check for closing positions
                if trigger != 0 and np.sign(trigger) != np.sign(current_utilisation):
                    pair_logger(f"checking for book profit - trigger: {trigger}, current_utilisation: {current_utilisation}")

                # check for adding to position
                if trigger != 0 and np.sign(trigger) == np.sign(current_utilisation):
                    additional_qty = get_additional_qty(qty_at_net_strength, current_units)
                    qty, sl_price, take_profit = self.strategy_manager.check_and_get_trade_qty(candles=candles,
                                                                                               trigger=trigger,
                                                                                               instrument=instrument,
                                                                                               qty=additional_qty,
                                                                                               pair_logger=pair_logger,
                                                                                               rejected_logger=rejected_logger,
                                                                                               trend_strength=net_strength,
                                                                                               pair_config=pair_config)
                    pair_logger(f"checking for adding to position - trigger: {trigger}, current_units: {current_units}, "
                                f"qty_at_net_strength: {qty_at_net_strength}, additional_qty: {additional_qty}")
                    if qty != 0:
                        trade_logger(f"Placed additional trade: qty: {qty}, trend_strength: {net_strength}")
                        self.base_api.place_order(pair, use_limit_order, qty, instrument, current_price,
                                                  get_expiry(pair_config.granularity), use_sl=True,
                                                  stop_loss=sl_price, take_profit=take_profit,
                                                  logger=self.logger.log_message)
                pass
            else:
                pair_logger(f"No check for trade. current_units: {current_units}, trigger: {trigger}")

        except Exception as e:
            self.logger.log_to_error(f"Error processing {pair}: {str(e)}")
            print(e)
            raise

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
            # self.process_pairs(self.trading_pairs)

            while True:
                try:
                    tm_mday = time.localtime().tm_mday
                    tm_hour = time.localtime().tm_hour
                    tm_min = time.localtime().tm_min
                    tm_sec = time.localtime().tm_sec

                    if tm_sec % 5 == 3:
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

