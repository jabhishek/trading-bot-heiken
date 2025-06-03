from config.constants import INITIAL_SL_PERIOD, TP_MULTIPLE
from models.open_trade import OpenTrade
from utils.get_prev_swing import get_previous_swing


def get_swing_stop_loss(direction, df) -> float | None:
    x = get_previous_swing(df, direction)
    return x['price'] if x is not None else None

def get_probable_stop_loss(direction, df, pipLocationPrecision, pair_logger, heikin_ashi):
    swing_sl = get_swing_stop_loss(direction, heikin_ashi)

    spread = (df["ask_c"] - df["bid_c"]).iloc[-1]
    price = df["mid_c"].iloc[-1]

    high = df["mid_h"].rolling(window=INITIAL_SL_PERIOD).max()
    low = df["mid_l"].rolling(window=INITIAL_SL_PERIOD).min()

    if direction > 0:
        donchian_sl = low.iloc[-1]
    else:
        donchian_sl = high.iloc[-1]

    sl_price = swing_sl if swing_sl is not None else donchian_sl

    if direction > 0:
        sl_price = sl_price - spread
    else:
        sl_price = sl_price + spread

    sl_price = round(sl_price, abs(pipLocationPrecision))
    sl_gap = round(abs(price - sl_price), abs(pipLocationPrecision))

    take_profit = price + sl_gap * TP_MULTIPLE if direction > 0 else price - sl_gap * TP_MULTIPLE
    take_profit = round(take_profit, abs(pipLocationPrecision))

    return sl_price, take_profit, sl_gap

def get_current_stop_value(trade: OpenTrade | None) -> float | None:
    stop_loss_price: str | None = None

    if trade is not None:
        stop_loss_order = trade.stopLossOrder

        if stop_loss_order is not None:
            stop_loss_price = stop_loss_order["price"]
    return float(stop_loss_price) if stop_loss_price is not None else None
