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
from models.trade_data import PotentialTrade, TradeData, TradeType
from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor
from token_info.token_watchlist import TokenWatchlist

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

    async def monitor_trades(self, watchlist):
        wallet_balance_native = self.wallet_manager.get_native_token_balance()
        trade_amount = int(
            wallet_balance_native * self.data_manager.config["trade_amount_percent"]
        )
        await self.buy_increasing_tokens_from_watchlist(
            trade_amount,
            watchlist,
        )
        await self.sell_decreasing_tokens_from_monitor()

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

    async def buy_increasing_tokens_from_watchlist(
        self,
        native_token_trade_amount_min,
        watchlist: TokenWatchlist,
    ):
        # Create a copy of the watchlist
        watchlist_copy = list(watchlist)

        for token in watchlist_copy:
            potential_trade = PotentialTrade(
                token["token_address"],
                token["pool_address"],
                token["fee"],
                token["token_base_value"],
            )
            logging.info(
                "buy_increasing_tokens_from_watchlist: checking duplicate monitored token"
            )

            if not self.is_duplicate(
                potential_trade.token_address, potential_trade.pool_address
            ):
                should_continue_watching = await self.process_increasing_token(
                    potential_trade, native_token_trade_amount_min
                )
                # Remove the token from watchlist if it should no longer be watched
                if not should_continue_watching:
                    await watchlist.remove(
                        potential_trade.token_address, potential_trade.pool_address
                    )
            else:
                logging.info(
                    f"buy_increasing_tokens_from_watchlist: watchlist token {token} is already in monitored token list"
                )

    async def process_increasing_token(
        self,
        potential_trade: PotentialTrade,
        native_token_trade_amount_min,
    ):
        logging.info(
            f"processing increasing token: watchlist token {potential_trade.token_address}"
        )

        # amount of tokens given for a amount of ETH
        current_token_amount = await self.protocol_manager.get_min_token_for_native(
            potential_trade.token_address,
            self.data_manager.config["trade_amount_min"],
            potential_trade.fee,
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
            Decimal(str(float(potential_trade.token_base_value)))
            / price_increase_threshold  # divide because its the opposite, less tokens if token is worth more in eth
        )
        logging.info(
            f"Token : {potential_trade.token_address}, "
            f"Current Token Amount: {current_token_amount:.0f}, "
            f"Threshold: {price_increase_threshold}, "
            f"Expected Token Amount: {threshold_token_amount:.0f}"
        )

        if current_token_amount < threshold_token_amount:  # less tokens; more valuable
            trade_data_buy = TradeData(
                trade_type=TradeType.BUY,
                input_amount=native_token_trade_amount_min,  # eg. 0.01 ETH
                expected_amount=None,  # to be calculated later
                original_investment_eth=native_token_trade_amount_min,
            )

            await self.trade_increasing_token(potential_trade, trade_data_buy)
            return False
        elif current_token_amount > 0:  # token price is still valid
            return True

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
            logging.info(
                f"No balance left to trade {potential_trade.token_address}, removing from watchlist."
            )

    async def sell_decreasing_tokens_from_monitor(self):
        logging.info("sell_decreasing_tokens_from_monitor: start")
        monitored_tokens = deepcopy(self.token_monitor.get_monitored_tokens())

        logging.info("sell_decreasing_tokens_from_monitor: checking monitored_tokens")

        # remove any orphaned tokens in the monitor
        for _, token_data in monitored_tokens.items():
            token_address = token_data["token_address"]
            pool_address = token_data["pool_address"]
            await self.check_monitored_valid(token_address, pool_address)

        for _, token_data in monitored_tokens.items():
            actual_token_balance = self.wallet_manager.get_token_balance(
                token_data["token_address"]
            )

            potential_trade = PotentialTrade(
                token_data["token_address"],
                token_data["pool_address"],
                token_data["fee"],
                token_data["token_base_value"],
            )

            logging.info(
                f"sell_decreasing_tokens_from_monitor: token: {potential_trade.token_address} fee: {potential_trade.fee} pool_address: {pool_address} token_base_value: {potential_trade.token_base_value}"
            )

            trade_data_sell = TradeData(
                trade_type=TradeType.SELL,
                input_amount=actual_token_balance,
                expected_amount=None,
                original_investment_eth=token_data["input_amount"],
            )

            await self.process_decreasing_token(
                potential_trade,
                trade_data_sell,
            )

    async def process_decreasing_token(
        self,
        potential_trade: PotentialTrade,
        trade_data: TradeData,
    ):
        logging.info("process_decreasing_token: start")
        # process the token prices for demo mode
        await self.protocol_manager.get_min_token_for_native(
            potential_trade.token_address,
            self.data_manager.config["trade_amount_min"],
            potential_trade.fee,
        )

        # amount in ETH we'd expect if we sold right now
        trade_data.expected_amount = (
            await self.protocol_manager.get_max_native_for_token(
                potential_trade.token_address,
                trade_data.input_amount,
                potential_trade.fee,
            )
        )

        # Check if token amount is negative or invalid
        if trade_data.expected_amount < 0:
            # Handle the error or invalid token amount
            logging.error("Invalid token amount. Cannot proceed further.")
            return  # or raise an exception, return an error code, or take appropriate action

        # check against amount paid for the tokens
        # did we make a ROI?
        current_roi_multiplier = (
            float(trade_data.expected_amount)
            / float(trade_data.original_investment_eth)  # eg. 0.08 / 0.06
            if potential_trade.token_base_value > 0
            else 0
        )

        expected_roi_multiplier = self.trade_evaluator.calculate_roi_multiplier(
            potential_trade, trade_data
        )

        has_reached_roi_or_decreased = (
            current_roi_multiplier > expected_roi_multiplier
        ) or (
            current_roi_multiplier
            < self.token_analysis.data_manager.config["price_decrease_threshold"]
        )

        # if self.blockchain_manager.get_current_chain().name == "goerli_testnet":
        #     has_reached_roi_or_decreased = True

        if has_reached_roi_or_decreased:
            await self.trade_decreasing_token(
                potential_trade,
                trade_data,
                current_roi_multiplier,
                expected_roi_multiplier,
            )
        else:
            await self.check_monitored_valid(
                potential_trade.token_address, potential_trade.pool_address
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
        logging.info(f"Token {potential_trade.token_address} sold due to {sold_reason}")

        # Check if token amount in ETH is negative or invalid; sometimes the token is worthless to sell
        if trade_data.expected_amount < 0:
            # Handle the error or invalid token amount
            logging.error(
                f"Invalid token amount {trade_data.expected_amount} to sell for. Cannot proceed further."
            )
            return  # or raise an exception, return an error code, or take appropriate action

        if self.trade_evaluator.has_balance_for_trade(
            potential_trade.token_address, trade_data.expected_amount, TradeAction.SELL
        ):
            await self.trade_executor.trade_token(
                potential_trade,
                trade_data,
                TradeAction.SELL,
            )
            await self.token_monitor.remove_monitored_token(
                potential_trade.token_address, potential_trade.pool_address
            )

    async def check_monitored_valid(self, token_address, pool_address):
        if self.demo_mode:
            if not self.wallet_manager.get_demo_mode_tokens().get(token_address):
                logging.info(
                    f"{token_address} is not in the token balance dictionary. \
                        Removing token {token_address} from monitored tokens"
                )
                await self.token_monitor.remove_monitored_token(
                    token_address, pool_address
                )
