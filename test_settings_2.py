SETTINGS = {
    "pairs":
        {
            "USD_JPY": {"granularity": "M15", "weight": 0.1},
            "EUR_USD": {"granularity": "M15", "weight": 0.1},
            "GBP_USD": {"granularity": "M15", "weight": 0.1},
            "SPX500_USD": {"granularity": "H1", "weight": 0.1},
            "CH20_CHF": {"granularity": "H1", "weight": 0.1},

            "WHEAT_USD": {"granularity": "H1", "weight": 0.1, "short_only": True},
            "NATGAS_USD": {"granularity": "H1", "weight": 0.1, "short_only": True},
            "SUGAR_USD": {"granularity": "H1", "weight": 0.1, "long_only": False},
            "BCO_USD": {"granularity": "H1", "weight": 0.1, "long_only": True},
            "SOYBN_USD": {"granularity": "H1", "weight": 0.1, "short_only": False},
            "CORN_USD": {"granularity": "H1", "weight": 0.1, "short_only": True},
            "XAU_USD": {"granularity": "H1", "weight": 0.1},

            # "USD_CAD": {"granularity": "H1", "weight": 0.1},
            #
            # "USD_CHF": {"granularity": "M15", "weight": 0.1},
            # "EUR_CHF": {"granularity": "H1", "weight": 0.1},
            #
            #
            # "HKD_JPY": {"granularity": "H1", "weight": 0.1},
            # "SGD_JPY": {"granularity": "H1", "weight": 0.1},
            # "GBP_JPY": {"granularity": "H1", "weight": 0.1},
            # "NZD_JPY": {"granularity": "H1", "weight": 0.1},
            # #
            # "EUR_JPY": {"granularity": "H1", "weight": 0.1},
            #
            # "SPX500_USD": {"granularity": "H1", "weight": 0.1},
            # "NAS100_USD": {"granularity": "H1", "weight": 0.1},

            "CN50_USD": {"granularity": "H1", "weight": 0.1},
            'XCU_USD': {'granularity': 'H1', 'weight': 0.1},
            # #
            #
            'XAG_USD': {'granularity': 'H1', 'weight': 0.1},
            #
            "UK10YB_GBP": {"granularity": "H1", "weight": 0.1},
            "USB10Y_USD": {"granularity": "H1", "weight": 0.1},
            "DE10YB_EUR": {"granularity": "H1", "weight": 0.1},
            # #
            #
            "USD_MXN": {"granularity": "H1", "weight": 0.1},
            # #
        },
    "std_lookback": 36,
    "polling_period": 1,
    "vol_target": 0.1
}
