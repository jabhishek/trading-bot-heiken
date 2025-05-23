from dataclasses import dataclass


@dataclass
class PositionData:
    instrument: str
    units: float
    unrealized_pl: float
    margin_used: float