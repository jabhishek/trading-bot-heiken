from utils.net_sma_trend import get_net_trend
from utils.no_op import no_op

INCREMENT = 0.1

def get_net_bullish_strength(price_series, logger, steps_logger):
    net_trend_200 = get_net_trend(price_series, 200).iloc[-1]
    net_trend_100 = get_net_trend(price_series, 100).iloc[-1]
    net_trend_50 = get_net_trend(price_series, 50).iloc[-1]
    net_trend_30 = get_net_trend(price_series, 30).iloc[-1]
    net_trend_10 = get_net_trend(price_series, 10).iloc[-1]

    current_price = price_series.iloc[-1]
    sma_200 = price_series.iloc[-200:].mean()
    sma_100 = price_series.iloc[-100:].mean()
    sma_50 = price_series.iloc[-50:].mean()
    sma_30 = price_series.iloc[-30:].mean()
    sma_10 = price_series.iloc[-10:].mean()

    steps_logger(f"net_trend_10: {net_trend_10}, net_trend_30: {net_trend_30}, net_trend_50: {net_trend_50}, net_trend_100: {net_trend_100}, net_trend_200: {net_trend_200}")

    bullish_strength = 0
    bearish_strength = 0

    if net_trend_200 > 0:
        steps_logger(f"bullish: net_trend_200 > 0")
        bullish_strength += 2*INCREMENT
    elif net_trend_200 < 0:
        steps_logger(f"bearish: net_trend_200 < 0")
        bearish_strength += 2*INCREMENT
    if sma_10 > sma_200:
        steps_logger(f"bullish: sma_10 > sma_200")
        bullish_strength += 2*INCREMENT
    elif sma_10 < sma_200:
        steps_logger(f"bearish: sma_10 < sma_200")
        bearish_strength += 2*INCREMENT
    if current_price > sma_200 and net_trend_200 > 0:
        steps_logger(f"bullish: current_price > sma_200 and net_trend_200 > 0")
        bullish_strength += 2 * INCREMENT
    if current_price < sma_200 and net_trend_200 < 0:
        steps_logger(f"bearish: current_price < sma_200 and net_trend_200 < 0")
        bearish_strength += 2 * INCREMENT

    if net_trend_100 > 0:
        steps_logger(f"bullish: net_trend_100 > 0")
        bullish_strength += INCREMENT
    elif net_trend_100 < 0:
        steps_logger(f"bearish: net_trend_100 < 0")
        bearish_strength += INCREMENT
    if sma_10 > sma_100:
        steps_logger(f"bullish: sma_10 > sma_100")
        bullish_strength += INCREMENT
    elif sma_10 < sma_100:
        steps_logger(f"bearish: sma_10 < sma_100")
        bearish_strength += INCREMENT
    if current_price > sma_100 and net_trend_100 > 0:
        steps_logger(f"bullish: current_price > sma_100 and net_trend_100 > 0")
        bullish_strength += INCREMENT
    if current_price < sma_100 and net_trend_100 < 0:
        steps_logger(f"bearish: current_price < sma_100 and net_trend_100 < 0")
        bearish_strength += INCREMENT

    if net_trend_50 > 0:
        steps_logger(f"bullish: net_trend_50 > 0")
        bullish_strength += 1.25*INCREMENT
    elif net_trend_50 < 0:
        steps_logger(f"bearish: net_trend_50 < 0")
        bearish_strength += 1.25*INCREMENT
    if current_price > sma_50:
        steps_logger(f"bullish: current_price > sma_50")
        bullish_strength += 1.25*INCREMENT
    elif current_price < sma_50:
        steps_logger(f"bearish: current_price < sma_50")
        bearish_strength += 1.25*INCREMENT
    if current_price > sma_50 and net_trend_50 > 0:
        steps_logger(f"bullish: current_price > sma_50 and net_trend_50 > 0")
        bullish_strength += 1.25 * INCREMENT
    elif current_price < sma_50 and net_trend_50 < 0:
        steps_logger(f"bearish: current_price < sma_50 and net_trend_50 < 0")
        bearish_strength += 1.25 * INCREMENT

    if net_trend_30 > 0:
        steps_logger(f"bullish: net_trend_30 > 0")
        bullish_strength += INCREMENT
    elif net_trend_30 < 0:
        steps_logger(f"bearish: net_trend_30 < 0")
        bearish_strength += INCREMENT
    if current_price > sma_30:
        steps_logger(f"bullish: current_price > sma_30")
        bullish_strength += INCREMENT
    elif current_price < sma_30:
        steps_logger(f"bearish: current_price < sma_30")
        bearish_strength += INCREMENT
    if current_price > sma_30 and net_trend_30 > 0:
        steps_logger(f"bullish: current_price > sma_30 and net_trend_30 > 0")
        bullish_strength += INCREMENT
    elif current_price < sma_30 and net_trend_30 < 0:
        steps_logger(f"bearish: current_price < sma_30 and net_trend_30 < 0")
        bearish_strength += INCREMENT

    logger(f"bullish_strength: {round(bullish_strength, 2)}, bearish_strength: {round(bearish_strength, 2)}")

    return bullish_strength, bearish_strength