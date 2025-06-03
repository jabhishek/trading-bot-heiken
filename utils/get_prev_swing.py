import numpy as np
import pandas as pd


def get_previous_swing(df: pd.DataFrame, trade_direction: int) -> dict | None:
    if df.empty:
        return None
    df = df.reset_index().copy()
    # ------------------------------------------------------------------
    # 1. Determine current trend (sign of the most-recent ha_streak)
    # ------------------------------------------------------------------
    current_streak = df.iloc[-1]['ha_streak']
    current_sign = np.sign(current_streak)
    if trade_direction != 0 and current_sign != trade_direction:
        print(f"Current trend sign {current_sign} does not match trade direction {trade_direction}.")
        return None

    looking_for_positive = current_sign < 0  # we are in a down-trend → need last positive streak segment
    opposite_mask_val = 1 if looking_for_positive else -1

    first_opposite_idx = None
    for i in range(len(df) - 2, -1, -1):  # start from the bar *before* the last one
        sign_i = np.sign(df.iloc[i]['ha_streak'])
        if sign_i != current_sign:
            first_opposite_idx = i
            break
        pass

    # ------------------------------------------------------------------
    # 2. Walk backward, collecting contiguous bars of the opposite sign
    # ------------------------------------------------------------------
    opposite_segment_idx = []

    for i in range(first_opposite_idx, -1, -1):  # start from the bar *before* the last one
        sign_i = np.sign(df.iloc[i]['ha_streak'])
        if sign_i == opposite_mask_val:
            opposite_segment_idx.append(i)
        else:
            # we reached a bar that is *not* part of the opposite segment
            break

    if not opposite_segment_idx:
        # No opposite-trend bars were found
        return None

    # ------------------------------------------------------------------
    # 3. Within that segment, find the extreme (min low / max high)
    # ------------------------------------------------------------------
    segment = df.loc[opposite_segment_idx]

    if looking_for_positive:  # current trend is down → swing high
        extreme_row = segment['ha_high'].idxmax()
        return {
            'type': 'swing_high',
            'index': int(extreme_row),
            'time': df.loc[extreme_row, 'time'],
            'price': float(df.loc[extreme_row, 'ha_high'])
        }
    else:  # current trend is up → swing low
        extreme_row = segment['ha_low'].idxmin()
        return {
            'type': 'swing_low',
            'index': int(extreme_row),
            'time': df.loc[extreme_row, 'time'],
            'price': float(df.loc[extreme_row, 'ha_low'])
        }
