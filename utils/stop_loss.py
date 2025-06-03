from config.constants import INITIAL_SL_PERIOD, TP_MULTIPLE
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
    pair_logger(f"Swing SL: {swing_sl}, donchian SL: {donchian_sl}, sl_price: {sl_price}")

    if direction > 0:
        sl_price = sl_price - spread
    else:
        sl_price = sl_price + spread
    pair_logger(f"Adjusted SL Price: {sl_price}")


    sl_price = round(sl_price, abs(pipLocationPrecision))
    sl_gap = round(abs(price - sl_price), abs(pipLocationPrecision))

    take_profit = price + sl_gap * TP_MULTIPLE if direction > 0 else price - sl_gap * TP_MULTIPLE
    take_profit = round(take_profit, abs(pipLocationPrecision))

    return sl_price, take_profit, sl_gap

def get_trailing_stop_loss(direction, df, pipLocationPrecision):
    spread = (df["ask_c"] - df["bid_c"]).iloc[-1]
    price = df["mid_c"].iloc[-1]
