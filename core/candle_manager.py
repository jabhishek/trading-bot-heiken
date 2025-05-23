from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import concurrent.futures

from api.OandaApi import OandaApi
from core.log_wrapper import LogManager


@dataclass
class CandleTiming:
    last_time: datetime
    granularity: str
    is_ready: bool = False
    completed_only: bool = True

    def __repr__(self):
        return f"last_candle:{self.last_time.strftime('%y-%m-%d %H:%M')} is_ready:{self.is_ready}"


class CandleManager:
    def __init__(self, pairs: List[str], api_client: OandaApi, pair_settings: Dict, logger: Optional[LogManager]):
        self.pairs = pairs
        self.api = api_client
        self.pair_settings = pair_settings
        self.logger = logger
        
        # Initialize timing information for each pair
        self.timings: Dict[str, CandleTiming] = {}
        self._initialize_timings()
        
        # Add flag to track if update is running
        self._is_updating = False

    def _initialize_timings(self) -> None:
        """Initialize timing information for all pairs."""
        for pair in self.pairs:
            try:
                last_time = self.api.last_complete_candle(
                    pair,
                    self.pair_settings[pair]["granularity"],
                    self.pair_settings[pair].get("completed_only", True)
                )
                if last_time is None:
                    self.logger.log_to_error(f"Could not initialize timing for {pair}")
                    continue
                    
                self.timings[pair] = CandleTiming(
                    last_time=last_time,
                    granularity=self.pair_settings[pair]["granularity"],
                    completed_only=self.pair_settings[pair].get("completed_only", True)
                )
            except Exception as e:
                self.logger.log_to_error(f"Error initializing timing for {pair}: {str(e)}")
                
    def update_timings(self) -> list[Any] | None:
        # Return empty list if already updating
        if self._is_updating:
            self.logger.log_message("*** Already updating, skipping update")
            return None

        triggered_pairs = []
        self._is_updating = True
        try:
            def process_pair(pair: str) -> Optional[str]:
                try:
                    timing = self.timings[pair]
                    current = self.api.last_complete_candle(
                        pair,
                        timing.granularity,
                        timing.completed_only
                    )
                    
                    if current is None:
                        self.logger.log_to_error(f"Unable to get candle for {pair}")
                        return None
                        
                    timing.is_ready = False
                    
                    # Check if we have a new candle
                    if not timing.completed_only or current > timing.last_time:
                        timing.is_ready = True
                        timing.last_time = current
                        return pair
                        
                except Exception as e:
                    self.logger.log_to_error(f"Error updating timing for {pair}: {str(e)}")
                    return None
                    
                return None
            
            # Process pairs in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_pair, pair) for pair in self.pairs]
                for future in concurrent.futures.as_completed(futures):
                    if pair := future.result():
                        triggered_pairs.append(pair)
                        self.logger.log_message(f"*** new candle: {triggered_pairs}", pair)

            return triggered_pairs
            
        finally:
            self._is_updating = False

    def get_timing(self, pair: str) -> Optional[CandleTiming]:
        """Get timing information for a specific pair."""
        return self.timings.get(pair)
        
    def reset_timing(self, pair: str) -> None:
        """Reset the ready state for a pair's timing."""
        if pair in self.timings:
            self.timings[pair].is_ready = False 