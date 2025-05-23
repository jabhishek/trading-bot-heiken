DEFAULT_STD_LOOKBACK = 36
DEFAULT_VOL_TARGET = 0.2
DEFAULT_POLLING_PERIOD = 30


class TradeSettings:
    def __init__(self, raw_settings):
        self.pair_settings = {k: v for k, v in raw_settings['pairs'].items()}
        self.pairs = self.pair_settings.keys()
        self.std_lookback = raw_settings.get('std_lookback', DEFAULT_STD_LOOKBACK)
        self.polling_period = raw_settings.get('polling_period', DEFAULT_POLLING_PERIOD)
        self.vol_target = raw_settings.get('vol_target', DEFAULT_VOL_TARGET)
        self.reduce_only = raw_settings.get('reduce_only', False)
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(std_lookback: {self.std_lookback}, polling_period: {self.polling_period}, vol_target: {self.vol_target}, pairs: {self.pairs})"
