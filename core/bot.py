import time
from typing import Any, List, Optional, Dict, Tuple
import concurrent.futures

import numpy as np
import pandas as pd
from typing_extensions import Callable

from api.OandaApi import OandaApi
from config.constants import ATR_KEY, SMA_PERIOD_LONG, SMA_PERIOD_SHORT
from core.StrategyManager import StrategyManager
from core.base_api import BaseAPI
from core.candle_manager import CandleManager
from core.log_wrapper import LogManager
from core.pair_config import PairConfig
from indicators.rsi import get_rsi
from models.TradeSettings import TradeSettings
from models.instrument_data import InstrumentData
from models.open_trade import OpenTrade
from models.position_data import PositionData
from utils.get_expiry import get_expiry
from utils.get_spread_threshold import get_spread_threshold
from utils.get_trade_ex_rate import get_trade_ex_rate
from utils.heiken_ashi import ohlc_to_heiken_ashi
from utils.net_sma_trend import get_net_trend
from utils.net_strength import get_net_bullish_strength, _compute_strength
from utils.no_op import no_op
from utils.sma_bands import check_band_position
from utils.stop_loss import get_current_stop_value, get_probable_stop_loss


def get_additional_qty(ideal_qty: float, current_position: float) -> float:
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
                f"********* {pair_config.granularity} {last_candle["time"]}*********")

            rsi = get_rsi(candles["mid_c"], 14)
            pair_logger(f"rsi: {rsi:.2f}")

            # Calculate indicators
            candles = self.base_api.calculate_indicators(candles, pair_config, pair_logger)

            candles["sma_200"] = candles["mid_c"].rolling(window=200).mean()
            candles["sma_100"] = candles["mid_c"].rolling(window=100).mean()
            candles["sma_50"] = candles["mid_c"].rolling(window=50).mean()
            candles["sma_30"] = candles["mid_c"].rolling(window=30).mean()
            candles["sma_10"] = candles["mid_c"].rolling(window=10).mean()

            candles["net_trend_200"] = get_net_trend(candles["mid_c"], 200)
            candles["net_trend_100"] = get_net_trend(candles["mid_c"], 100)
            candles["net_trend_50"] = get_net_trend(candles["mid_c"], 50)
            candles["net_trend_30"] = get_net_trend(candles["mid_c"], 30)
            net_trend_30: int = candles["net_trend_30"].iloc[-1]

            candles[['bearish_strength', 'bullish_strength']] = candles.apply(_compute_strength, axis=1)
            # (Optional) inspect the result
            candles['bearish_strength_s'] = candles['bearish_strength'].ewm(span=10, adjust=False).mean()
            candles['bullish_strength_s'] = candles['bullish_strength'].ewm(span=10, adjust=False).mean()
            candles['net_strength'] = candles['bullish_strength'] - candles['bearish_strength']
            candles['net_strength_s'] = candles['bullish_strength_s'] - candles['bearish_strength_s']

            bullish_strength = candles['bullish_strength'].iloc[-1]
            bearish_strength = candles['bearish_strength'].iloc[-1]
            net_strength = bullish_strength - bearish_strength

            pair_logger(f"bearish_strength: {np.array(round(candles['bearish_strength'].tail(10), 2))}")
            pair_logger(f"bullish_strength: {np.array(round(candles['bullish_strength'].tail(10), 2))}")
            pair_logger(f"bearish_strength smoothed: {np.array(round(candles['bearish_strength_s'].tail(10), 2))}")
            pair_logger(f"bullish_strength smoothed: {np.array(round(candles['bullish_strength_s'].tail(10), 2))}")
            pair_logger(f"net_strength: {np.array(round(candles['net_strength'].tail(10), 2))}")
            pair_logger(f"net_strength smoothed: {np.array(round(candles['net_strength_s'].tail(10), 2))}")

            atr = candles.iloc[-1][ATR_KEY]
            pl_multiple = np.abs(round(pl * ex_rate / (current_units * atr), 2)) if current_units != 0 else 0
            pair_logger(f"units: {current_units:.2f}, pl: {pl:.2f}, pl_multiple: {pl_multiple:.2f}")

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

            # bullish_strength, bearish_strength = get_net_bullish_strength(candles["mid_c"], logger=pair_logger, steps_logger=no_op)
            # net_strength = bullish_strength - bearish_strength

            # qty_at_net_strength = base_qty * net_strength
            pair_logger(f"net_strength: {round(net_strength, 2)}")
            heikin_ashi: pd.DataFrame = ohlc_to_heiken_ashi(candles.iloc[-100:].copy())

            trigger = self.strategy_manager.check_for_trigger(heikin_ashi, pair_logger)

            # look for new positions
            if current_units == 0 and trigger != 0:
                pair_logger(f"checking for trade - trigger: {trigger}")
                should_trade, sl_price, take_profit = self.strategy_manager.check_and_get_trade_qty(candles=candles, trigger=trigger, instrument=instrument,
                                                                               pair_logger=pair_logger, rejected_logger=rejected_logger,
                                                                               pair_config=pair_config, heikin_ashi=heikin_ashi,
                                                                            sma_trend_30=net_trend_30, rsi=rsi)
                pair_logger(f"should_trade: {should_trade}, sl_price: {sl_price}, take_profit: {take_profit}")
                if should_trade:
                    ideal_qty: float = self.get_ideal_qty(base_qty, bearish_strength, bullish_strength, trigger)
                    if ideal_qty!= 0:
                        qty = self.get_trade_qty(base_qty, ideal_qty, pair_logger)
                        trade_logger(f"Placed trade: qty: {round(qty, 2)}, ideal_qty: {round(ideal_qty, 2)}, bullish_strength: {round(bullish_strength, 2)}, bearish_strength: {round(bearish_strength, 2)}, net_trend_30: {net_trend_30}, rsi: {rsi:.2f}")
                        self.base_api.place_order(pair, use_limit_order, qty, instrument, current_price,
                                                  get_expiry(pair_config.granularity), use_sl=True,
                                                  stop_loss=sl_price, take_profit=None, logger=self.logger.log_message)
                    else:
                        rejected_logger(f"ideal_qty is 0, not placing trade. ideal_qty: {round(ideal_qty, 2)}, bearish_strength: {bearish_strength}, bullish_strength: {bullish_strength}, trigger: {trigger}")
            elif current_units != 0:
                trades: List[OpenTrade] = self.base_api.get_trades(pair)
                self.update_stop_loss(trades, current_units, candles, instrument, pair_logger, heikin_ashi, trade_logger, rejected_logger, pl, pl_multiple)

                # check for closing position
                self.check_close_trades(pair, candles, pair_config, instrument,
                                        ex_rate, pair_logger, current_price, trigger, trade_logger, trades)

                # check for adding to position
                if trigger != 0 and np.sign(trigger) == np.sign(current_units):
                    should_trade, sl_price, take_profit = self.strategy_manager.check_and_get_trade_qty(candles=candles,
                                                                                               trigger=trigger,
                                                                                               instrument=instrument,
                                                                                               pair_logger=pair_logger,
                                                                                               rejected_logger=rejected_logger,
                                                                                               pair_config=pair_config, heikin_ashi=heikin_ashi, sma_trend_30=net_trend_30, rsi=rsi)
                    if should_trade:
                        ideal_qty = self.get_ideal_qty(base_qty, bearish_strength, bullish_strength, trigger)
                        spare_qty: float = get_additional_qty(ideal_qty, current_units)
                        pair_logger(f"ideal_qty: {round(ideal_qty, 2)}, spare_qty: {round(spare_qty, 2)}, current_units: {round(current_units, 2)}")
                        if spare_qty != 0:
                            additional_qty = self.get_trade_qty(base_qty, spare_qty, pair_logger)
                            pair_logger(
                                f"additional_qty: {round(additional_qty, 2)}, ideal_qty: {round(ideal_qty, 2)}, spare_qty: {round(spare_qty, 2)}")

                            trade_logger(f"Placed additional trade: qty: {round(additional_qty, 2)}, bullish_strength: {round(bullish_strength, 2)}, bearish_strength: {round(bearish_strength, 2)}, net_trend_30: {net_trend_30}, rsi: {rsi:.2f}")
                            self.base_api.place_order(pair, use_limit_order, additional_qty, instrument, current_price,
                                                      get_expiry(pair_config.granularity), use_sl=True,
                                                      stop_loss=sl_price, take_profit=None,
                                                      logger=self.logger.log_message)
                        else:
                            rejected_logger(f"spare_qty is 0, not placing additional trade. ideal_qty: {round(ideal_qty, 2)}, spare_qty: {round(spare_qty, 2)}, current_units: {round(current_units, 2)}, trigger: {trigger}")
            else:
                pair_logger(f"No check for trade. current_units: {round(current_units, 2)}, trigger: {trigger}")

        except Exception as e:
            self.logger.log_to_error(f"Error processing {pair}: {str(e)}")
            print(e)
            raise

    def get_trade_qty(self, base_qty, spare_qty, pair_logger):
        max_qty = base_qty * 0.5
        pair_logger(f"max_qty: {round(max_qty, 2)}, spare_qty: {round(spare_qty, 2)}")
        additional_qty = np.sign(spare_qty) * min(abs(spare_qty), max_qty)
        return additional_qty

    def get_ideal_qty(self, base_qty, bearish_strength, bullish_strength, trigger) -> float:
        qty = base_qty * bullish_strength if trigger > 0 else -1 * base_qty * bearish_strength
        return qty

    def update_stop_loss(self, trades: List[OpenTrade], current_units, candles, instrument, pair_logger, heikin_ashi,
                         trade_logger, rejected_logger, pl, pl_multiple) -> None:
        trade_direction = np.sign(current_units)
        new_fixed_sl, take_profit, sl_gap = get_probable_stop_loss(trade_direction, candles,
                                                               instrument.pipLocationPrecision, pair_logger, heikin_ashi)
        for t in trades:
            # atr = candles.iloc[-1][ATR_KEY]
            # pl = t.unrealizedPL
            # pl_multiple = np.abs(round(pl * ex_rate / (t.currentUnits * atr), 2)) if t.currentUnits != 0 else 0

            current_sl_price, updated_sl = self.get_updated_sl(new_fixed_sl, t)

            if current_sl_price is None or updated_sl != current_sl_price:
                if pl > 0 and pl_multiple > 1:
                    pair_logger(
                        f"updating stop_loss {current_sl_price} -> {float(updated_sl)}, pl: {pl:.2f}, pl_multiple: {pl_multiple:.2f}")
                    self.api_client.update_fixed_stop_loss(t.id, new_fixed_sl, True)
                else:
                    pair_logger(f"not updating stop_loss, pl: {pl:.2f}, pl_multiple: {pl_multiple:.2f}, qty: {t.currentUnits:.2f}")

    def get_updated_sl(self, new_fixed_sl, t):
        current_sl_price = get_current_stop_value(t)
        if t.currentUnits > 0:
            updated_sl = max(new_fixed_sl, current_sl_price)
        else:
            updated_sl = min(new_fixed_sl, current_sl_price)
        return current_sl_price, updated_sl

    def check_close_trades(self, pair, candles, pair_config: PairConfig, instrument: InstrumentData,
                           ex_rate: float, pair_logger, current_price: float, trigger: int, trade_logger, trades: List[OpenTrade]):
        atr = candles.iloc[-1][ATR_KEY]
        for t in trades:
            qty_to_close = self.strategy_manager.check_for_closing_trade(t, ex_rate, atr, trigger, pair_logger)

            if qty_to_close != 0:
                self.base_api.place_order(pair, True, qty_to_close, instrument, current_price,
                                          get_expiry(pair_config.granularity), use_sl=False,
                                          logger=self.logger.log_message)
                trade_logger(f"book profit - trigger: {trigger}, qty_to_trade: {qty_to_close}")

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

                    if tm_sec % 5 < 2:
                        print(f"---- {tm_mday} {tm_hour}:{tm_min}:{tm_sec}")
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


