from config.constants import INITIAL_SL_PERIOD, TP_MULTIPLE


def get_probable_stop_loss(direction, df, pipLocationPrecision):
    spread = (df["ask_c"] - df["bid_c"]).iloc[-1]
    price = df["mid_c"].iloc[-1]

    high = df["mid_h"].rolling(window=INITIAL_SL_PERIOD).max()
    low = df["mid_l"].rolling(window=INITIAL_SL_PERIOD).min()

    if direction > 0:
        sl_price = low.iloc[-1] - spread
    else:
        sl_price = high.iloc[-1] + spread

    sl_price = round(sl_price, abs(pipLocationPrecision))
    sl_gap = round(abs(price - sl_price), abs(pipLocationPrecision))

    take_profit = price + sl_gap * TP_MULTIPLE if direction > 0 else price - sl_gap * TP_MULTIPLE
    take_profit = round(take_profit, abs(pipLocationPrecision))

    return sl_price, take_profit, sl_gap

def get_trailing_stop_loss(direction, df, pipLocationPrecision):
    spread = (df["ask_c"] - df["bid_c"]).iloc[-1]
    price = df["mid_c"].iloc[-1]
