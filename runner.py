from api.OandaApi import OandaApi
from core.base_api import BaseAPI
from core.bot import Bot
from test_settings_2 import SETTINGS as settings
from core.StrategyManager import StrategyManager
import api.constants_test_1 as account_settings
from models.TradeSettings import TradeSettings

if __name__ == "__main__":

    api_client: OandaApi = OandaApi(api_key=account_settings.API_KEY, account_id=account_settings.ACCOUNT_ID,
                                         url=account_settings.OANDA_URL)
    base_api: BaseAPI = BaseAPI(api_client)
    trade_settings = TradeSettings(settings)
    strategy_manager = StrategyManager(api_client, trade_settings, base_api=base_api)
    bot = Bot(api_client=api_client, trade_settings=trade_settings, bot_name="live_db_sm_v2",
              strategy_manager=strategy_manager, base_api=base_api)
    bot.run()