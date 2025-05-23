from core.bot import Bot
from test_settings_2 import SETTINGS as settings
import api.constants_test_1 as account_settings
from models.TradeSettings import TradeSettings

if __name__ == "__main__":
    trade_settings = TradeSettings(settings)
    bot = Bot(account_settings=account_settings, trade_settings=trade_settings, bot_name="live_db_sm_v2")
    bot.run()