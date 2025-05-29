def get_expiry(granularity: str):
    interval_mapping = {
        "H4": 60 * 4 * 60,
        "H1": 60 * 60,
        "M30": 30 * 60,
        "M15": 15 * 60,
        "M5": 5 * 60,
        "M1": 60,
    }
    return interval_mapping[granularity]
