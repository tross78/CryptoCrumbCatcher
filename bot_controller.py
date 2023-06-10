from decimal import Decimal
from os.path import dirname, join

from dotenv import load_dotenv

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.trade_controller import TradeController
from managers.trade_evaluator import TradeEvaluator
from managers.trade_executor import TradeExecutor
from managers.wallet_manager import WalletManager
from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)


class BotController:
    MAX_TOKENS_MONITORED = 5

    def __init__(
        self, data_manager, user_selected_chain=None, reset_userdata_on_load=True
    ):
        self.data_manager = data_manager

        self.demo_mode = self.data_manager.config["demo_mode"]

        self.blockchain_manager: BlockchainManager = BlockchainManager(
            user_selected_chain
        )
        self.protocol_manager: ProtocolManager = ProtocolManager(
            self.blockchain_manager, self.demo_mode
        )

        self.wallet_manager: WalletManager = WalletManager(
            self.blockchain_manager,
            self.data_manager,
            self.demo_mode,
            reset_userdata_on_load,
        )
        self.token_monitor = TokenMonitor(
            self.blockchain_manager.get_current_chain().name,
            self.wallet_manager,
            reset_userdata_on_load,
        )
        self.token_analysis: TokenAnalysis = TokenAnalysis(
            self.data_manager, self.blockchain_manager, self.protocol_manager
        )

        self.trade_executor: TradeExecutor = TradeExecutor(
            self.blockchain_manager,
            self.token_monitor,
            self.wallet_manager,
            self.protocol_manager,
            self.demo_mode,
        )
        self.profit_margin = Decimal(str(self.data_manager.config["profit_margin"]))

        self.trade_evaluator: TradeEvaluator = TradeEvaluator(
            self.blockchain_manager,
            self.data_manager,
            self.wallet_manager,
            self.protocol_manager,
            self.profit_margin,
        )

        self.trade_manager: TradeController = TradeController(
            self.data_manager,
            self.token_analysis,
            self.token_monitor,
            self.blockchain_manager,
            self.wallet_manager,
            self.protocol_manager,
            self.profit_margin,
            self.trade_executor,
            self.trade_evaluator,
            self.demo_mode,
        )
