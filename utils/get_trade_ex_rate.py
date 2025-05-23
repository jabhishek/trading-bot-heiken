def get_trade_ex_rate(pair, api):
    base_currency, traded_currency = pair.split('_')
    ex_rate = 1
    if traded_currency != 'GBP':
        p = f"GBP_{traded_currency}"
        base_to_trade_currency = api.get_price(p)
        if base_to_trade_currency is not None:
            ex_rate = base_to_trade_currency.bid

    return ex_rate
