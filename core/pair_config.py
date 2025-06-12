from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PairConfig:
    pair: str
    settings: Dict[str, Any]
    
    @property
    def granularity(self) -> str:
        return self.settings.get("granularity", "M30")
    
    @property
    def weight(self) -> float:
        return self.settings.get("weight", 0.1)
    
    @property
    def long_only(self) -> bool:
        return self.settings.get("long_only", False)
    
    @property
    def short_only(self) -> bool:
        return self.settings.get("short_only", False)

    def get_raw_settings(self) -> Dict[str, Any]:
        return self.settings

    def __repr__(self) -> str:
        return f"PairConfig(pair={self.pair}, settings={self.settings})"