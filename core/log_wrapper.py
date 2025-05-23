import logging
import os
from datetime import datetime
from typing import Dict, Optional, Callable


class LogWrapper:
    """Wrapper class for managing multiple log files."""
    
    BASE_PATH = './logs'
    LOG_FORMAT = "%(asctime)s %(message)s"
    DEFAULT_LEVEL = logging.DEBUG
    
    def __init__(self, bot_name: str, log_name: str, current_time: str, mode: str = "a"):
        """
        Initialize a log wrapper.
        
        Args:
            bot_name: Name of the bot instance
            log_name: Name of this specific log
            current_time: Current date in YYYY-MM-DD format
            mode: File mode for the log file ('a' for append, 'w' for write)
        """
        # Create directory structure
        dir_path = os.path.join(self.BASE_PATH, bot_name, current_time)
        os.makedirs(dir_path, exist_ok=True)
        
        # Setup log file
        self.filename = os.path.join(dir_path, f"{log_name}.log")
        self.logger = logging.getLogger(f"{bot_name}.{log_name}")
        self.logger.setLevel(self.DEFAULT_LEVEL)
        
        # Create and configure file handler
        file_handler = logging.FileHandler(self.filename, mode=mode)
        formatter = logging.Formatter(self.LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Log initialization
        self.logger.info(f"LogWrapper initialized at {datetime.now().strftime('%m/%d/%Y %H:%M:%S')} - {self.filename}")

class LogManager:
    """
    Manages multiple log files for different purposes in the trading system.
    
    This class provides a centralized logging system that handles:
    1. Multiple Log Types:
       - Error logs: For system errors and exceptions
       - Main logs: For general system information
       - Trade logs: For trading-related events
       - Pair-specific logs: For individual pair activities
    
    2. Logging Functions:
       - log_message: General logging to specific and main logs
       - log_trade: Trade-specific logging
       - log_to_main: Main system logging
       - log_to_error: Error logging
    
    3. Log Builders:
       - log_message_builder: Creates pair-specific loggers
       - log_trade_builder: Creates trade-specific loggers
    
    Example:
        >>> # Initialize with bot name and pairs
        >>> logger = LogManager(
        ...     bot_name="my_bot",
        ...     pairs=["EUR_USD", "GBP_USD"]
        ... )
        >>> # Get pair-specific logger
        >>> pair_logger = logger.log_message_builder("EUR_USD")
        >>> pair_logger("New candle received")
        >>> # Log trade
        >>> trade_logger = logger.log_trade_builder("EUR_USD")
        >>> trade_logger("Entered long position")
    """
    
    def __init__(self, bot_name: str, pairs: list[str]):
        """
        Initialize the log manager.
        
        Args:
            bot_name (str): Name of the bot instance for log file organization
            pairs (list[str]): List of trading pairs to create logs for
        
        The initialization process:
        1. Creates base log files (error, main, trades)
        2. Creates pair-specific log files
        3. Sets up logging format and handlers
        4. Initializes logging configuration
        
        Log files are organized in the following structure:
        ./logs/{bot_name}/{date}/{log_type}.log
        """
        self.bot_name = bot_name
        self.current_time = datetime.now().strftime("%Y-%m-%d")
        
        # Create base logs
        self.logs: Dict[str, LogWrapper] = {
            "error": LogWrapper(bot_name, "error", self.current_time),
            "main": LogWrapper(bot_name, "main", self.current_time),
            "trades": LogWrapper(bot_name, "trades", self.current_time),
            "rejected": LogWrapper(bot_name, "rejected", self.current_time)
        }
        
        # Create pair-specific logs
        for pair in pairs:
            self.logs[pair] = LogWrapper(bot_name, pair, self.current_time)
            
        # Log initialization
        self.log_to_main(f"Bot started with pairs: {pairs}")
        
    def log_message(self, msg: str, key: str) -> None:
        """Log a message to both the specific log and main log."""
        print(f"{key}: {msg}")
        self.logs[key].logger.debug(f"{key}: {msg}")
        self.logs["main"].logger.debug(f"{key}: {msg}")

    def log_message_builder(self, key: str) -> Callable[[str], None]:
        def log_message_with_key(msg: str) -> None:
            self.log_message(msg, key)

        return log_message_with_key

    def log_trade(self, msg: str, key: str, granularity: str) -> None:
        """Log a trade message to the specific log, trades log, and main log."""
        print(f"{key}: {msg}")
        self.logs[key].logger.debug(f"{key}: {msg}")
        self.logs["trades"].logger.debug(f"{key} {granularity}: {msg}")
        self.logs["main"].logger.debug(f"{key}: {msg}")

    def log_trade_builder(self, key: str, granularity) -> Callable[[str], None]:
        def log_trade_with_key(msg: str) -> None:
            self.log_trade(msg, key, granularity)

        return log_trade_with_key

    def log_rejected(self, msg: str, key: str, granularity: str) -> None:
        """Log a trade message to the specific log, rejected log, and main log."""
        print(f"{key}: {msg}")
        self.logs[key].logger.debug(f"{key}: {msg}")
        self.logs["rejected"].logger.debug(f"{key} {granularity}: {msg}")
        self.logs["main"].logger.debug(f"{key}: {msg}")

    def log_rejected_builder(self, key: str, granularity) -> Callable[[str], None]:
        def log_rejected_with_key(msg: str) -> None:
            self.log_rejected(msg, key, granularity)

        return log_rejected_with_key

    def log_to_main(self, msg: str) -> None:
        """Log a message only to the main log."""
        print(msg)
        self.logs["main"].logger.debug(msg)

    def log_to_error(self, msg: str) -> None:
        """Log an error message."""
        print(f"error: {msg}")
        self.log_message(msg, "error")
        
    def get_logger(self, key: str) -> Optional[logging.Logger]:
        """Get the logger for a specific key."""
        if wrapper := self.logs.get(key):
            return wrapper.logger
        return None 