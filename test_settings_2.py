SETTINGS = {
    "pairs":
        {
            "USD_CAD": {"granularity": "H1", "weight": 0.1, "short_only": False},
            "WHEAT_USD": {"granularity": "H1", "weight": 0.1, "short_only": False},

            "NATGAS_USD": {"granularity": "H1", "weight": 0.1, "short_only": False},

            "SUGAR_USD": {"granularity": "H1", "weight": 0.1, "long_only": False},
            "BCO_USD": {"granularity": "H1", "weight": 0.1, "long_only": False},

            "USD_CHF": {"granularity": "M30", "weight": 0.1},
            "EUR_CHF": {"granularity": "M30", "weight": 0.1},
            "USD_JPY": {"granularity": "M30", "weight": 0.1},
            "EUR_USD": {"granularity": "M5", "weight": 0.1},
            "HKD_JPY": {"granularity": "M30", "weight": 0.1},
            "GBP_USD": {"granularity": "M30", "weight": 0.1},
            "SGD_JPY": {"granularity": "M30", "weight": 0.1},
            "GBP_JPY": {"granularity": "M30", "weight": 0.1},
            "NZD_JPY": {"granularity": "M30", "weight": 0.1},
            #
            "EUR_JPY": {"granularity": "M30", "weight": 0.01},

            "SPX500_USD": {"granularity": "M30", "weight": 0.1},
            "NAS100_USD": {"granularity": "M30", "weight": 0.1},
            "CH20_CHF": {"granularity": "M30", "weight": 0.1},
            "CN50_USD": {"granularity": "M30", "weight": 0.1},
            "XAU_USD": {"granularity": "M30", "weight": 0.1},
            'XCU_USD': {'granularity': 'M30', 'weight': 0.1},
            #

            'XAG_USD': {'granularity': 'M30', 'weight': 0.1},

            "UK10YB_GBP": {"granularity": "H1", "weight": 0.1},
            "USB10Y_USD": {"granularity": "H1", "weight": 0.1},
            "DE10YB_EUR": {"granularity": "H1", "weight": 0.1},
            #

            "USD_MXN": {"granularity": "M30", "weight": 0.1},
            #
            "SOYBN_USD": {"granularity": "H1", "weight": 0.1, "short_only": False},
            "CORN_USD": {"granularity": "H1", "weight": 0.1, "short_only": False},
        },
    "std_lookback": 36,
    "polling_period": 2,
    "vol_target": 0.25
}
