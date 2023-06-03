import logging
from copy import deepcopy
from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.trade_evaluator import TradeEvaluator
from managers.trade_executor import TradeExecutor
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor
from token_info.token_watchlist import TokenWatchlist
from utils import has_value_increased

logging.basicConfig(
    filename="trade.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


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

    async def monitor_trades(self, factory_contract, watchlist):
        self.add_increasing_tokens_to_monitor(
            factory_contract.address,
            self.blockchain_manager.get_current_chain().native_token_address,
            self.data_manager.config["trade_amount_wei"],
            watchlist,
        )
        self.sell_decreasing_tokens_from_monitor(
            factory_contract.address,
            self.blockchain_manager.get_current_chain().native_token_address,
        )

    def is_duplicate(self, token_address, pool_address):
        token_pool_id = f"{token_address}_{pool_address}"
        monitored_tokens = self.token_monitor.get_monitored_tokens()

        for token_pool_id, obj in monitored_tokens.items():
            logging.info(f"Type of obj: {type(obj)}")  # Check the type of obj
            if not isinstance(obj, dict):
                logging.warning(f"obj is not a dictionary: {obj}")
                continue
            if "token_address" not in obj or "pool_address" not in obj:
                logging.warning(f"obj doesn't have expected keys: {obj}")
                continue
            if f'{obj["token_address"]}_{obj["pool_address"]}' == token_pool_id:
                return True
        return False

    def add_increasing_tokens_to_monitor(
        self,
        factory_address,
        native_token_address,
        native_token_trade_amount,
        watchlist: TokenWatchlist,
    ):
        # Create a copy of the watchlist
        watchlist_copy = list(watchlist)

        for token in watchlist_copy:
            token_address = token["token_address"]
            pool_address = token["pool_address"]
            logging.info(
                "add_increasing_tokens_to_monitor: checking duplicate monitored token"
            )

            if not self.is_duplicate(token_address, pool_address):
                should_continue_watching = self.process_increasing_token(
                    factory_address,
                    token_address,
                    pool_address,
                    native_token_address,
                    native_token_trade_amount,
                    token,
                )
                # Remove the token from watchlist if it should no longer be watched
                if not should_continue_watching:
                    watchlist.remove(token_address, pool_address)
            else:
                logging.info(
                    f"add_increasing_tokens_to_monitor: watchlist token {token} is already in monitored token list"
                )

    def process_increasing_token(
        self,
        factory_address,
        token_address,
        pool_address,
        native_token_address,
        native_token_trade_amount,
        token,
    ):
        logging.info(f"processing increasing token: watchlist token {token}")

        fee = token["fee"]
        initial_token_amount = token["initial_token_amount"]

        current_token_amount = self.protocol_manager.get_min_token_for_native(
            token_address, self.data_manager.config["trade_amount_wei"], fee
        )

        # Check if token amount is negative or invalid, -1 is invalid or error
        if current_token_amount < 0:
            # Handle the error or invalid token amount
            logging.error("Invalid token amount. Cannot proceed further.")
            return  # or raise an exception, return an error code, or take appropriate action

        price_increase_threshold = Decimal(
            str(self.data_manager.config["price_increase_threshold"])
        )
        threshold_token_amount = (
            Decimal(str(float(initial_token_amount)))
            / price_increase_threshold  # divide because its the opposite, less tokens if token is worth more in eth
        )
        logging.info(
            f"Token : {token_address}, "
            f"Current Token Amount: {current_token_amount:.0f}, "
            f"Threshold: {price_increase_threshold}, "
            f"Expected Token Amount: {threshold_token_amount:.0f}"
        )

        if current_token_amount < threshold_token_amount:  # less tokens; more valuable
            self.trade_increasing_token(
                token_address,
                pool_address,
                native_token_address,
                fee,
                native_token_trade_amount,
                factory_address,
                initial_token_amount,
                current_token_amount,
            )
            return False
        elif current_token_amount > 0:  # token price is still valid
            return True

    def trade_increasing_token(
        self,
        token_address,
        pool_address,
        native_token_address,
        fee,
        native_token_trade_amount,
        factory_address,
        initial_token_amount,
        current_token_amount,
    ):
        if self.trade_evaluator.has_balance_for_trade(
            token_address, native_token_trade_amount, TradeAction.BUY
        ):
            self.trade_executor.trade_token(
                factory_address,
                token_address,
                pool_address,
                fee,
                native_token_address,
                native_token_trade_amount,
                initial_token_amount,
                current_token_amount,
                TradeAction.BUY,
            )

        else:
            logging.info(
                f"No balance left to trade {token_address}, removing from watchlist."
            )

    def sell_decreasing_tokens_from_monitor(
        self, factory_address, native_token_address
    ):
        monitored_tokens = deepcopy(self.token_monitor.get_monitored_tokens())

        for _, token_data in monitored_tokens.items():
            token_address = token_data["token_address"]
            fee = token_data["fee"]
            pool_address = token_data["pool_address"]
            initial_token_amount = token_data.get("initial_token_amount", 0)

            self.process_decreasing_token(
                factory_address,
                token_address,
                native_token_address,
                fee,
                pool_address,
                initial_token_amount,
            )

    def process_decreasing_token(
        self,
        factory_address,
        token_address,
        native_token_address,
        fee,
        pool_address,
        initial_token_amount,
    ):
        # do a pre-check for the price just in case its zero or has an error
        current_token_amount = self.protocol_manager.get_min_token_for_native(
            token_address, self.data_manager.config["trade_amount_wei"], fee
        )

        # Check if token amount is negative or invalid
        if current_token_amount < 0:
            # Handle the error or invalid token amount
            logging.error("Invalid token amount. Cannot proceed further.")
            return  # or raise an exception, return an error code, or take appropriate action

        current_roi_multiplier = (
            float(current_token_amount) / float(initial_token_amount)
            if initial_token_amount > 0
            else 0
        )

        price_decrease_ratio = (
            float(initial_token_amount) / float(current_token_amount)
            if current_token_amount > 0
            else 1
        )

        expected_roi_multiplier = self.trade_evaluator.calculate_roi_multiplier(fee)

        logging.info(
            f"Selling decreasing tokens: current_price: {current_token_amount}, \
                initial_token_amount:{initial_token_amount}, current_roi_multiplier: {current_roi_multiplier}, \
                    expected_multiplier:{expected_roi_multiplier}"
        )

        if has_value_increased(
            current_roi_multiplier, expected_roi_multiplier
        ) or has_value_increased(
            self.token_analysis.data_manager.config["price_decrease_threshold"],
            price_decrease_ratio,
        ):
            self.sell_token(
                factory_address,
                token_address,
                native_token_address,
                pool_address,
                fee,
                initial_token_amount,
                current_token_amount,
                current_roi_multiplier,
                expected_roi_multiplier,
            )
        else:
            self.check_token_balance(token_address, pool_address)

    def sell_token(
        self,
        factory_address,
        token_address,
        native_token_address,
        pool_address,
        fee,
        initial_token_amount,
        current_token_amount,
        current_roi_multiplier,
        expected_roi_multiplier,
    ):
        sold_reason = "reaching desired ROI"
        if current_roi_multiplier < expected_roi_multiplier:
            sold_reason = "price decrease"
        logging.info(f"Token {token_address} sold due to {sold_reason}")
        if not self.wallet_manager.get_tokens().get(token_address):
            logging.info(
                f"{token_address} is not in the token balance dictionary. \
                    Removing token {token_address} from monitored tokens"
            )
            self.token_monitor.remove_monitored_token(token_address, pool_address)
        else:
            trade_amount = self.wallet_manager.get_token_balance(
                token_address
            )  # trade entire balance of token in wallet
            # native_token_amount = self.protocol_manager.get_min_token_for_native(
            #     token_address, token_balance, fee
            # )
            token_amount_in_eth = self.protocol_manager.get_max_native_for_token(
                token_address, trade_amount, fee
            )
            # Check if token amount in ETH is negative or invalid; sometimes the token is worthless to sell
            if token_amount_in_eth < 0:
                # Handle the error or invalid token amount
                logging.error(
                    f"Invalid token amount {token_amount_in_eth} to sell for. Cannot proceed further."
                )
                return  # or raise an exception, return an error code, or take appropriate action

            if self.trade_evaluator.has_balance_for_trade(
                token_address, trade_amount, TradeAction.SELL
            ):
                # self.trade_executor.trade_token(
                #     token_address, fee, token_amount, TradeAction.SELL
                # )
                # trade_amount = amount in token
                # token_amount = amount in eth
                self.trade_executor.trade_token(
                    factory_address,
                    token_address,
                    pool_address,
                    fee,
                    native_token_address,
                    trade_amount,
                    initial_token_amount,
                    current_token_amount,
                    TradeAction.SELL,
                )
                self.token_monitor.remove_monitored_token(token_address, pool_address)

    def check_token_balance(self, token_address, pool_address):
        if not self.wallet_manager.get_tokens().get(token_address):
            logging.info(
                f"{token_address} is not in the token balance dictionary. \
                    Removing token {token_address} from monitored tokens"
            )
            self.token_monitor.remove_monitored_token(token_address, pool_address)
