from dataclasses import dataclass
from typing import Dict, Any

from config.constants import DEFAULT_DBL_SM_PERIOD, DEFAULT_DBL_SM_1, DEFAULT_DBL_SM_2


@dataclass
class PairConfig:
    """
    Configuration class for managing pair-specific trading settings and constraints.
    
    This class encapsulates all configuration parameters for a single trading pair,
    including trading constraints, technical indicator settings, and risk parameters.
    
    Key Configuration Options:
    1. Trading Constraints:
       - long_only: Restrict trading to long positions only
       - short_only: Restrict trading to short positions only
       - weight: Portfolio weight allocation
    
    2. Technical Indicators:
       - granularity: Timeframe for analysis (e.g., "M1", "M5", "H1")
       - dbl_sm_period: Double smoothing period
       - dbl_sm_1: First smoothing parameter
       - dbl_sm_2: Second smoothing parameter
    
    3. Risk Management:
       - weight: Portfolio allocation percentage
       - trading constraints (long_only/short_only)
    
    Example:
        >>> # Create configuration for a long-only pair
        >>> config = PairConfig(
        ...     pair="EUR_USD",
        ...     settings={
        ...         "granularity": "M1",
        ...         "weight": 0.2,
        ...         "long_only": True,
        ...         "dbl_sm_period": 1,
        ...         "dbl_sm_1": 5,
        ...         "dbl_sm_2": 20
        ...     }
        ... )
        >>> # Access configuration values
        >>> print(config.granularity)  # "M1"
        >>> print(config.weight)  # 0.2
        >>> print(config.long_only)  # True
    """
    
    pair: str
    settings: Dict[str, Any]
    
    @property
    def granularity(self) -> str:
        """
        Get the granularity setting for the pair.
        
        Returns:
            str: Timeframe for analysis (e.g., "M1", "M5", "H1")
                Defaults to "M30" if not specified
        """
        return self.settings.get("granularity", "M30")
    
    @property
    def weight(self) -> float:
        """
        Get the weight setting for the pair.
        
        Returns:
            float: Portfolio weight allocation (0.0 to 1.0)
                Defaults to 0.1 if not specified
        """
        return self.settings.get("weight", 0.1)
    
    @property
    def long_only(self) -> bool:
        """
        Check if the pair is restricted to long positions only.
        
        Returns:
            bool: True if only long positions are allowed
                Defaults to False if not specified
        """
        return self.settings.get("long_only", False)
    
    @property
    def short_only(self) -> bool:
        """
        Check if the pair is restricted to short positions only.
        
        Returns:
            bool: True if only short positions are allowed
                Defaults to False if not specified
        """
        return self.settings.get("short_only", False)
    
    @property
    def dbl_sm_period(self) -> int:
        """
        Get the double smoothing period setting.
        
        Returns:
            int: Period for double smoothing calculation
                Defaults to DEFAULT_DBL_SM_PERIOD if not specified
        """
        return self.settings.get("dbl_sm_period", DEFAULT_DBL_SM_PERIOD)
    
    @property
    def dbl_sm_1(self) -> int:
        """
        Get the first double smoothing parameter.
        
        Returns:
            int: First smoothing parameter
                Defaults to DEFAULT_DBL_SM_1 if not specified
        """
        return self.settings.get("dbl_sm_1", DEFAULT_DBL_SM_1)
    
    @property
    def dbl_sm_2(self) -> int:
        """
        Get the second double smoothing parameter.
        
        Returns:
            int: Second smoothing parameter
                Defaults to DEFAULT_DBL_SM_2 if not specified
        """
        return self.settings.get("dbl_sm_2", DEFAULT_DBL_SM_2)
    
    def get_raw_settings(self) -> Dict[str, Any]:
        """
        Get the raw settings dictionary.
        
        Returns:
            Dict[str, Any]: Complete settings dictionary for the pair
        """
        return self.settings 