import asyncio
from decimal import Decimal
from venv import logger

from models.trade_data import PotentialTrade, TradeData, TradeType


class BuyHandler:
    def __init__(
        self,
        blockchain_manager,
        protocol_manager,
        data_manager,
        token_monitor,
        wallet_manager,
        trade_controller,
    ):
        self.blockchain_manager = blockchain_manager
        self.protocol_manager = protocol_manager
        self.data_manager = data_manager
        self.token_monitor = token_monitor
        self.wallet_manager = wallet_manager
        self.trade_controller = trade_controller

    async def buy_increasing_tokens(self, trade_amount, watchlist):
        # Create a copy of the watchlist
        watchlist_copy = list(watchlist)
        # Create tasks for all tokens
        tasks = [
            self.process_increasing_token(token_data, trade_amount, watchlist)
            for token_data in watchlist_copy
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    async def process_increasing_token(
        self, token_data, native_token_trade_amount, watchlist
    ):
        potential_trade = PotentialTrade(
            token_data["token"]["id"],
            token_data["token"]["name"],
            token_data["pool"]["id"],
            token_data["fee"]["basis_points"],
            token_data["token_base_value"],
        )
        logger.info(
            "buy_increasing_tokens_from_watchlist: checking duplicate monitored token"
        )

        # if (
        #     potential_trade.token_address.lower()
        #     == "0x6982508145454ce325ddbe47a25d4ec3d2311933"
        # ):
        #     abc = "123"

        if (
            not self.has_been_bought_already(
                potential_trade.token_address, potential_trade.pool_address
            )
            and self.is_below_token_monitor_limit()
        ):
            should_continue_watching = await self.evaluate_increasing_token(
                potential_trade, native_token_trade_amount
            )
            logger.info(
                f"watchlist token {potential_trade.token_address} has decreased 10%, removing from watchlist"
            )
            # Remove the token from watchlist if it should no longer be watched
            if not should_continue_watching:
                await watchlist.remove(
                    potential_trade.token_address, potential_trade.pool_address
                )
        else:
            logger.info(
                f"buy_increasing_tokens_from_watchlist: watchlist token {potential_trade.token_address} is already in monitored token list, removing from watchlist"
            )
            await watchlist.remove(
                potential_trade.token_address, potential_trade.pool_address
            )

    def is_below_token_monitor_limit(self):
        monitored_tokens = self.token_monitor.get_monitored_tokens()
        monitor_limit = self.data_manager.config["monitor_token_limit"]
        below_limit = len(monitored_tokens.items()) < monitor_limit
        return below_limit

    def has_been_bought_already(self, token_address, pool_address):
        passed_token_pool_id = f"{token_address}_{pool_address}"
        monitored_tokens = self.token_monitor.get_monitored_tokens()

        for token_pool_id, obj in monitored_tokens.items():
            if not isinstance(obj, dict):
                logger.warning(f"obj is not a dictionary: {obj}")
                continue
            if "token_address" not in obj or "pool_address" not in obj:
                logger.warning(f"obj doesn't have expected keys: {obj}")
                continue
            if token_pool_id == passed_token_pool_id:
                return True
        return False

    async def evaluate_increasing_token(
        self,
        potential_trade: PotentialTrade,
        native_token_trade_amount,
    ):
        logger.info(
            f"processing increasing token: watchlist token {potential_trade.token_address}"
        )

        # amount of tokens given for a amount of ETH
        current_token_amount = await self.protocol_manager.get_min_token_for_native(
            potential_trade.token_address,
            native_token_trade_amount,
            potential_trade.fee,
        )

        gas_limit_per_transaction = self.blockchain_manager.gas_limit_per_transaction
        # Get the current gas price in Gwei
        gas_price_wei = self.blockchain_manager.web3_instance.eth.gas_price
        gas_cost_per_transaction_wei = gas_price_wei * gas_limit_per_transaction

        # Avoid ZeroDivisionError
        if native_token_trade_amount == 0:
            logger.error("Native token trade amount is zero, aborting.")
            return

        gas_percentage_of_trade = float(gas_cost_per_transaction_wei) / float(
            native_token_trade_amount
        )

        gas_cost_trade_threshold = float(
            self.data_manager.config["gas_cost_trade_threshold"]
        )

        if gas_percentage_of_trade > gas_cost_trade_threshold:
            logger.error(
                f"Gas cost percentage {gas_percentage_of_trade * 100} exceeds { gas_cost_trade_threshold * 100}% of trade amount, aborting."
            )
            return

        # Check if token amount is negative or invalid, -1 is invalid or error
        if current_token_amount < 0:
            # Handle the error or invalid token amount
            logger.error("Invalid token amount. Cannot proceed further.")
            return  # or raise an exception, return an error code, or take appropriate action

        price_increase_threshold = Decimal(
            str(self.data_manager.config["price_increase_threshold"])
        )
        price_decrease_threshold = Decimal(
            str(self.data_manager.config["price_decrease_threshold"])
        )
        increased_threshold_token_amount = (
            Decimal(str(float(potential_trade.token_base_value)))
            / price_increase_threshold  # divide because its the opposite, less tokens if token is worth more in eth
        )
        decreased_threshold_token_amount = Decimal(
            str(float(potential_trade.token_base_value))
        ) * (
            Decimal(str(float(1 / price_decrease_threshold)))
        )  # divide because its the opposite, less tokens if token is worth more in eth

        logger.info(
            f"Token : {potential_trade.token_address}, "
            f"Current Token Amount: {current_token_amount:.0f}, "
            f"Increase Threshold: {price_increase_threshold}, "
            f"Decrease Threshold: {price_decrease_threshold}, "
            f"Decreased Amount To Remove from Watchlist: {decreased_threshold_token_amount:.0f}, "
            f"Expected Token Amount: {increased_threshold_token_amount:.0f}"
        )

        # Remove from watchlist if current value in eth is less than what is on the watchlist
        if potential_trade.token_base_value > decreased_threshold_token_amount:
            return False

        if (
            current_token_amount < increased_threshold_token_amount
        ):  # less tokens; more valuable
            trade_data_buy = TradeData(
                trade_type=TradeType.BUY,
                input_amount=native_token_trade_amount,  # eg. 0.01 ETH
                expected_amount=None,  # to be calculated later
                original_investment_eth=native_token_trade_amount,
            )

            await self.buy(potential_trade, trade_data_buy)
            # dont watch anymore, lets buy
            return False
        if current_token_amount > 0:  # token price is still valid
            return True

    async def buy(self, potential_trade, trade_data):
        # Some code
        await self.trade_controller.trade_increasing_token(potential_trade, trade_data)
