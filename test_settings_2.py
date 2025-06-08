SETTINGS = {
    "pairs":
        {
            "USD_CAD": {"granularity": "H1", "weight": 0.1},
            "WHEAT_USD": {"granularity": "H4", "weight": 0.1, "short_only": True},

            "NATGAS_USD": {"granularity": "H4", "weight": 0.1, "short_only": True},

            "SUGAR_USD": {"granularity": "H4", "weight": 0.1, "long_only": True},
            "BCO_USD": {"granularity": "H4", "weight": 0.1, "long_only": True},

            "USD_CHF": {"granularity": "M15", "weight": 0.1},
            "EUR_CHF": {"granularity": "H1", "weight": 0.1},
            "USD_JPY": {"granularity": "M15", "weight": 0.1},
            "EUR_USD": {"granularity": "M15", "weight": 0.1, "short_only": False},
            "HKD_JPY": {"granularity": "H1", "weight": 0.1},
            "GBP_USD": {"granularity": "H1", "weight": 0.1},
            "SGD_JPY": {"granularity": "H1", "weight": 0.1},
            "GBP_JPY": {"granularity": "H1", "weight": 0.1},
            "NZD_JPY": {"granularity": "H1", "weight": 0.1},
            #
            "EUR_JPY": {"granularity": "H1", "weight": 0.1},

            "SPX500_USD": {"granularity": "H1", "weight": 0.1},
            "NAS100_USD": {"granularity": "H1", "weight": 0.1},
            "CH20_CHF": {"granularity": "H1", "weight": 0.1},
            "CN50_USD": {"granularity": "H1", "weight": 0.1},
            "XAU_USD": {"granularity": "H1", "weight": 0.1},
            'XCU_USD': {'granularity': 'H1', 'weight': 0.1},
            #

            'XAG_USD': {'granularity': 'H1', 'weight': 0.1},

            "UK10YB_GBP": {"granularity": "H4", "weight": 0.1},
            "USB10Y_USD": {"granularity": "H4", "weight": 0.1},
            "DE10YB_EUR": {"granularity": "H4", "weight": 0.1},
            #

            "USD_MXN": {"granularity": "H1", "weight": 0.1},
            #
            "SOYBN_USD": {"granularity": "H4", "weight": 0.1, "short_only": True},
            "CORN_USD": {"granularity": "H4", "weight": 0.1, "short_only": True},
        },
    "std_lookback": 36,
    "polling_period": 1,
    "vol_target": 0.25
}
