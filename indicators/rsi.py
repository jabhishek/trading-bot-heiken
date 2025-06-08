import pandas as pd


def get_rsi_series(prices: pd.Series, n=14) -> pd.Series:
    alpha = 1.0 / n
    gains = prices.diff()

    wins = pd.Series([x if x >= 0 else 0.0 for x in gains], name="wins")
    losses = pd.Series([x * -1 if x < 0 else 0.0 for x in gains], name="losses")

    wins_rma = wins.ewm(min_periods=n, alpha=alpha).mean()
    losses_rma = losses.ewm(min_periods=n, alpha=alpha).mean()

    rs = wins_rma / losses_rma

    rsi = 100.0 - (100.0 / (1.0 + rs))
    #
    # print("gains", gains.tail())
    # print("wins", wins.tail())
    # print("losses", losses.tail())
    # print("wins_rma", wins_rma.tail())
    # print("losses_rma", losses_rma.tail())
    # print("rsi", rsi.tail())

    return rsi


def get_rsi(prices: pd.Series, n: int) -> float:
    return get_rsi_series(prices, n).iloc[-1]

#
# if __name__ == "__main__":
#     __oanda_api__ = OandaApi(account_id=ACCOUNT_ID, api_key=API_KEY, url=OANDA_URL)
#     def get_data(pair, granularity, source="oanda"):
#         if source == "oanda":
#             return __oanda_api__.get_candles_df(pair, completed_only=False, granularity=granularity,
#                                                 count=5000)
#         else:
#             filename = f"../data/{pair}_{granularity}.pkl"
#             return pd.read_pickle(filename)
#
#
#     __pair = "USD_JPY"
#     __granularity = "D"
#     # __data = __oanda_api__.get_candles_df(__pair, granularity=__granularity, count=5000)
#     __data = get_data(__pair, __granularity, source="oanda")
#     __data.set_index("time", inplace=True)
#     __data = __data[["mid_c", "bid_c", "ask_c"]].copy()
#     __data.dropna(inplace=True)
#     __data["rsi"] = get_rsi_series(__data["mid_c"], 10).values
#     print(__data)
