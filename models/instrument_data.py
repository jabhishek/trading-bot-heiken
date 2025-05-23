from dataclasses import dataclass
from typing import Dict


@dataclass
class InstrumentData:
    name: str
    ins_type: str
    displayName: str
    pipLocationPrecision: int
    pipLocation: int
    tradeUnitsPrecision: int
    marginRate: float
    displayPrecision: int
    minimumTrailingStopDistance: float
    maximumTrailingStopDistance: float

    def __post_init__(self):
        """Initialize derived properties after dataclass initialization."""
        self.pipLocation = pow(10, self.pipLocationPrecision)
        self.marginRate = float(self.marginRate)
        self.minimumTrailingStopDistance = float(self.minimumTrailingStopDistance)
        self.maximumTrailingStopDistance = float(self.maximumTrailingStopDistance)

    @classmethod
    def from_api_object(cls, api_object: Dict) -> 'InstrumentData':
        return cls(
            name=api_object['name'],
            ins_type=api_object['type'],
            displayName=api_object['displayName'],
            pipLocationPrecision=api_object['pipLocation'],
            pipLocation=0,  # Will be set in __post_init__
            tradeUnitsPrecision=api_object['tradeUnitsPrecision'],
            marginRate=api_object['marginRate'],
            displayPrecision=api_object['displayPrecision'],
            minimumTrailingStopDistance=api_object['minimumTrailingStopDistance'],
            maximumTrailingStopDistance=api_object['maximumTrailingStopDistance']
        )

