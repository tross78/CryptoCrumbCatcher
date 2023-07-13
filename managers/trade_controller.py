from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from logger_config import logger
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.trade_buy_handler import BuyHandler
from managers.trade_evaluator import TradeEvaluator
from managers.trade_executor import TradeExecutor
from managers.trade_sell_handler import SellHandler
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
from models.trade_data import PotentialTrade, TradeData
from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor


class TradeController:
    def __init__(
        self,
        data_manager: DataManagement,
        token_analysis: TokenAnalysis,
        token_monitor: TokenMonitor,
        blockchain_manager: BlockchainManager,
        wallet_manager: WalletManager,
        protocol_manager: ProtocolManager,
        profit_margin: Decimal,
        trade_executor: TradeExecutor,
        trade_evaluator: TradeEvaluator,
        demo_mode=True,
    ):
        self.demo_mode = demo_mode
        self.data_manager: DataManagement = data_manager
        self.token_analysis: TokenAnalysis = token_analysis
        self.token_monitor = token_monitor
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.wallet_manager: WalletManager = wallet_manager
        self.profit_margin: Decimal = profit_margin
        self.trade_executor: TradeExecutor = trade_executor
        self.trade_evaluator: TradeEvaluator = trade_evaluator
        self.protocol_manager: ProtocolManager = protocol_manager
        self.buy_handler = BuyHandler(
            self.blockchain_manager,
            self.protocol_manager,
            self.data_manager,
            self.token_monitor,
            self.wallet_manager,
            self,
        )
        self.sell_handler = SellHandler(
            self.demo_mode,
            self.blockchain_manager,
            self.protocol_manager,
            self.data_manager,
            self.token_monitor,
            self.wallet_manager,
            self.token_analysis,
            self.trade_evaluator,
            self,
        )

    async def monitor_trades(self, watchlist):
        trade_amount = int(
            self.wallet_manager.get_native_token_balance_percentage(
                self.data_manager.config["trade_amount_percentage"]
            )
        )
        await self.buy_handler.buy_increasing_tokens(
            trade_amount,
            watchlist,
        )
        await self.sell_handler.sell_decreasing_tokens()

    async def trade_increasing_token(
        self, potential_trade: PotentialTrade, trade_data: TradeData
    ):
        if self.trade_evaluator.has_balance_for_trade(
            potential_trade.token_address, trade_data.input_amount, TradeAction.BUY
        ):
            await self.trade_executor.trade_token(
                potential_trade,
                trade_data,
                TradeAction.BUY,
            )

        else:
            logger.info(
                f"No balance left to trade {potential_trade.token_address}, removing from watchlist."
            )

    async def trade_decreasing_token(
        self,
        potential_trade: PotentialTrade,
        trade_data: TradeData,
        current_roi_multiplier,
        expected_roi_multiplier,
    ):
        sold_reason = "reaching desired ROI"
        if current_roi_multiplier < expected_roi_multiplier:
            sold_reason = "price decrease"
        logger.info(f"Token {potential_trade.token_address} sold due to {sold_reason}")

        # Check if token amount in ETH is negative or invalid; sometimes the token is worthless to sell
        if trade_data.expected_amount < 0:
            # Handle the error or invalid token amount
            logger.error(
                f"Invalid token amount {trade_data.expected_amount} to sell for. Cannot proceed further."
            )
            return  # or raise an exception, return an error code, or take appropriate action

        if self.trade_evaluator.has_balance_for_trade(
            # input = tokens to trade for ETH in your wallet
            potential_trade.token_address,
            trade_data.input_amount,
            TradeAction.SELL,
        ):
            await self.trade_executor.trade_token(
                potential_trade,
                trade_data,
                TradeAction.SELL,
            )
            logger.info(
                f"Removing token {potential_trade.token_address} from the monitored tokens list due to being sold"
            )

            await self.token_monitor.remove_monitored_token(
                potential_trade.token_address, potential_trade.pool_address
            )
