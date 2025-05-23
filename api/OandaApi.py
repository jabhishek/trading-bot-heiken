import datetime
import math

import numpy as np
import requests
import pandas as pd
import json

from dateutil import parser
from datetime import datetime as dt
from datetime import timedelta

from models.api_price import ApiPrice
from models.open_trade import OpenTrade


def get_round_qty(units, tradeUnitsPrecision):
    sign = np.sign(units)
    abs_units = np.abs(units)

    # round_units = round(units, instrument.tradeUnitsPrecision)
    units = sign * math.floor(abs_units * 10 ** tradeUnitsPrecision) / 10 ** tradeUnitsPrecision

    return units


def get_trailing_sl(limit_gap, instrument):
    min_gap = float(instrument.minimumTrailingStopDistance)
    distance = max(limit_gap, min_gap)

    return dict(distance=str(distance))


class OandaApi:
    def __init__(self, account_id, api_key, url):
        self.account_id = account_id
        self.url = url
        self.api_key = api_key

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def make_request(self, url, verb='get', code=200, params=None, data=None, headers=None):
        full_url = f"{self.url}/{url}"

        if data is not None:
            data = json.dumps(data)

        try:
            response = None
            if verb == "get":
                response = self.session.get(full_url, params=params, data=data, headers=headers)
            if verb == "post":
                response = self.session.post(full_url, params=params, data=data, headers=headers)
            if verb == "put":
                response = self.session.put(full_url, params=params, data=data, headers=headers)
            if verb == "patch":
                response = self.session.patch(full_url, params=params, data=data, headers=headers)

            if response is None:
                return False, {'error': 'verb not found'}

            if response.status_code == code:
                return True, response.json()
            else:
                return False, response.json()
        except requests.exceptions.RequestException as error:
            print('RequestException', error)
            return False, {'Exception': error}
        except Exception as error:
            print('Exception', error)
            return False, {'Exception': error}

    def get_account_ep(self, ep, data_key):
        url = f"accounts/{self.account_id}/{ep}"
        ok, data = self.make_request(url)

        if ok and data_key in data:
            return data[data_key]
        else:
            print("ERROR get_account_ep()", data)
            return None

    def get_account_summary(self):
        return self.get_account_ep("summary", "account")

    def get_account_details(self):
        return self.get_account_ep("", "account")

    def get_account_instruments(self):
        return self.get_account_ep("instruments", "instruments")

    def get_instrument_position(self, instrument):
        url = f"accounts/{self.account_id}/positions/{instrument}"
        ok, data = self.make_request(url)

        if ok and 'position' in data:
            position = data['position']
            long_units = float(position.get('long', {}).get('units', '0'))
            short_units = float(position.get('short', {}).get('units', '0'))
            unrealizedPL = float(position.get('unrealizedPL', '0'))
            return long_units + short_units, unrealizedPL

        else:
            if 'errorCode' in data and data['errorCode'] == 'NO_SUCH_POSITION':
                return 0, 0
            else:
                print("ERROR get_instrument_position()", data, instrument)
                return None, None

    def fetch_candles(self, pair_name, count=10, granularity="H1",
                      price="MBA", date_f=None, date_t=None):
        url = f"instruments/{pair_name}/candles"
        params = dict(
            granularity=granularity,
            price=price
        )

        if date_f is not None and date_t is not None:
            date_format = "%Y-%m-%dT%H:%M:%SZ"
            params["from"] = dt.strftime(date_f, date_format)
            params["to"] = dt.strftime(date_t, date_format)
        else:
            params["count"] = count

        ok, data = self.make_request(url, params=params)

        if ok and 'candles' in data:
            return data['candles']
        else:
            print("ERROR fetch_candles()", params, data)
            return None

    def get_candles_df(self, pair_name, completed_only=False, **kwargs):

        data = self.fetch_candles(pair_name, **kwargs)

        if data is None:
            return None
        if len(data) == 0:
            return pd.DataFrame()

        prices = ['mid', 'bid', 'ask']
        ohlc = ['o', 'h', 'l', 'c']

        final_data = []
        for candle in data:
            if completed_only and candle['complete'] is False:
                continue
            new_dict = {}
            new_dict['time'] = parser.parse(candle['time'])
            new_dict['volume'] = candle['volume']
            for p in prices:
                if p in candle:
                    for o in ohlc:
                        new_dict[f"{p}_{o}"] = float(candle[p][o])
            final_data.append(new_dict)
        df = pd.DataFrame.from_dict(final_data)
        return df

    def last_complete_candle(self, pair_name, granularity, completed_only):
        df = self.get_candles_df(pair_name, granularity=granularity, completed_only=completed_only, count=10)
        if df is None or df.shape[0] == 0:
            return None
        return df.iloc[-1].time

    def latest_price(self, pair_name, granularity):
        df = self.get_candles_df(pair_name, granularity=granularity, completed_only=False, count=1)
        if df is None or df.shape[0] == 0:
            return None
        return df.iloc[-1].mid_c

    def place_trade(self, pair_name: str, units: float, instrument,
                    fixed_sl: float = None, use_stop_loss: bool = False,
                    trailing_stop_gap: float = None, logger=None, take_profit=None):

        url = f"accounts/{self.account_id}/orders"
        units = get_round_qty(units, instrument.tradeUnitsPrecision)

        if units == 0:
            if logger is not None:
                logger(f"**** No units to place {pair_name}", pair_name)
            return None

        order_dict = dict(
                units=str(units),
                instrument=pair_name,
                type="MARKET",
            )

        if use_stop_loss and trailing_stop_gap:
            order_dict["trailingStopLossOnFill"] = get_trailing_sl(trailing_stop_gap, instrument)
        if use_stop_loss and fixed_sl:
            order_dict["stopLossOnFill"] = dict(price=str(fixed_sl))
        if take_profit is not None:
            order_dict["takeProfitOnFill"] = dict(price=str(take_profit))

        data = dict(
            order=order_dict
        )
        logger(f"**** Placing market order: {units}", pair_name)
        ok, response = self.make_request(url, verb="post", data=data, code=201)
        if ok and 'orderFillTransaction' in response:
            if logger is not None:
                logger(f"**** Market Order placed: {units}, {response['orderFillTransaction']}", pair_name)
            return response['orderFillTransaction']['id']
        else:
            logger(f"**** Market order not placed {response.keys()}", pair_name)
            if 'errorCode' in response:
                logger(f"**** error code {response['errorCode']}", pair_name)
            if 'errorMessage' in response:
                logger(f"**** error message {response['errorMessage']}", pair_name)
            if 'orderCancelTransaction' in response:
                logger(f"**** cancel reason {response['orderCancelTransaction']['reason']}", pair_name)
            if 'orderRejectTransaction' in response:
                logger(f"**** reject reason {response['orderRejectTransaction']['reason']}", pair_name)
                logger(f"**** reject reason {response['errorMessage']}", pair_name)
            return None

    def place_limit_order(self, pair_name: str, units: float, price: float, expire_in_seconds: float,
                          instrument, fixed_sl: float = None, use_stop_loss: bool = False,
                          trailing_stop_gap: float = None, take_profit=None, logger=None):

        url = f"accounts/{self.account_id}/orders"

        units = get_round_qty(units, instrument.tradeUnitsPrecision)

        if units == 0:
            return None

        # get a time 2 minutes from now in UTC
        expiry = dt.now(datetime.UTC) + timedelta(seconds=expire_in_seconds)
        expiry = expiry.replace(second=0, microsecond=0).isoformat()

        order_dict = dict(
            units=str(units),
            instrument=pair_name,
            type="LIMIT",
            price=str(price),
            timeInForce="GTD",
            gtdTime=expiry,
        )

        if use_stop_loss and trailing_stop_gap:
            order_dict["trailingStopLossOnFill"] = get_trailing_sl(trailing_stop_gap, instrument)
        if use_stop_loss and fixed_sl:
            order_dict["stopLossOnFill"] = dict(price=str(fixed_sl))
        if take_profit is not None:
            order_dict["takeProfitOnFill"] = dict(price=str(take_profit))

        data = dict(
            order=order_dict
        )

        logger(f"**** Placing Limit Order: {units}", pair_name)
        ok, response = self.make_request(url, verb="post", data=data, code=201)
        if ok and 'orderCreateTransaction' in response:
            if logger is not None:
                logger(f"**** Limit order placed: {units}, {response['orderCreateTransaction']}", pair_name)

            return response['orderCreateTransaction']['id']
        else:
            logger(f"**** Limit order not placed {response.keys()}, {response['errorMessage']}", pair_name)
            return None

    def close_trade(self, trade_id):
        url = f"accounts/{self.account_id}/trades/{trade_id}/close"
        ok, _ = self.make_request(url, verb="put", code=200)

        if ok:
            print(f"Closed {trade_id} successfully")
        else:
            print(f"Failed to close {trade_id}")

        return ok

    def update_leverage(self, leverage=5):
        url = f"accounts/{self.account_id}/configuration"
        params = dict(marginRate=str(1/leverage))
        ok, response = self.make_request(url, verb="patch", code=200, data=params)

        if ok:
            print(f"Updated leverage successfully")
        else:
            print(f"Failed to update leverage", response)

        return ok

    def close_position(self, pair, qty, tradeUnitsPrecision: int):
        url = f"accounts/{self.account_id}/positions/{pair}/close"

        units = get_round_qty(qty, tradeUnitsPrecision)
        params = dict()
        if qty > 0:
            params['longUnits'] = str(units)
        if qty < 0:
            params['shortUnits'] = str(abs(units))
        print(f"closing units: {params}")

        ok, response = self.make_request(url, verb="put", code=200, data=params)
        if ok:
            print(f"Closed {pair} successfully")
        else:
            print(f"Failed to close {pair}", response)

        return ok

    def get_open_trades(self):
        url = f"accounts/{self.account_id}/openTrades"
        ok, response = self.make_request(url)

        if ok and 'trades' in response:
            return [OpenTrade(x) for x in response['trades']]

    def get_trades_for_instrument(self, pair, state="OPEN"):
        url = f"accounts/{self.account_id}/trades"

        params = dict(
            instrument=pair,
            state=state
        )
        ok, response = self.make_request(url, params=params)

        if ok and 'trades' in response:
            return [OpenTrade(x) for x in response['trades']]

    def update_trailing_stop_loss(self, trade_id, distance, use_stop_loss):
        trailingStopLoss = dict(distance=str(distance)) if use_stop_loss else None
        url = f"accounts/{self.account_id}/trades/{trade_id}/orders"
        body = dict(trailingStopLoss=trailingStopLoss)

        ok, response = self.make_request(url, data=body, verb="put", code=200)
        print(response)

        return ok, response

    def update_fixed_stop_loss(self, trade_id, price, use_stop_loss):
        stopLoss = dict(price=str(price)) if use_stop_loss else None
        url = f"accounts/{self.account_id}/trades/{trade_id}/orders"
        body = dict(stopLoss=stopLoss)

        ok, response = self.make_request(url, data=body, verb="put", code=200)
        print(response)

        return ok, response

    def get_prices(self, instruments_list):
        url = f"accounts/{self.account_id}/pricing"

        params = dict(
            instruments=','.join(instruments_list),
            includeHomeConversions=True
        )

        ok, response = self.make_request(url, params=params)

        if ok and 'prices' in response and 'homeConversions' in response:
            return [ApiPrice(x, response['homeConversions']) for x in response['prices']]

        return None

    def get_price(self, instrument) -> ApiPrice or None:
        prices = self.get_prices([instrument])
        if prices is None:
            return None
        else:
            return prices[0]
