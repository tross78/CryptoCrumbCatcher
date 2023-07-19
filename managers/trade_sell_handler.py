import asyncio
from copy import deepcopy
from venv import logger

from models.trade_data import PotentialTrade, TradeData, TradeType


class SellHandler:
    def __init__(
        self,
        demo_mode,
        blockchain_manager,
        protocol_manager,
        data_manager,
        token_monitor,
        wallet_manager,
        token_analysis,
        trade_evaluator,
        trade_controller,
    ):
        self.demo_mode = demo_mode
        self.blockchain_manager = blockchain_manager
        self.protocol_manager = protocol_manager
        self.data_manager = data_manager
        self.token_monitor = token_monitor
        self.wallet_manager = wallet_manager
        self.token_analysis = token_analysis
        self.trade_evaluator = trade_evaluator
        self.trade_controller = trade_controller

    async def sell_decreasing_tokens(self):
        logger.info("sell_decreasing_tokens_from_monitor: start")

        # remove any orphaned tokens in the monitor
        monitored_tokens = self.token_monitor.get_monitored_tokens()
        for token_pool_id, token_data in monitored_tokens.items():
            token_address = token_data["token_address"]
            pool_address = token_data["pool_address"]
            logger.info(
                "Checking monitored token valid: From sell_decreasing_tokens_from_monitor"
            )
            # TODO: FIX removal of monitored tokens
            await self.check_monitored_valid(token_address, pool_address)

        monitored_tokens = deepcopy(self.token_monitor.get_monitored_tokens())

        logger.info("sell_decreasing_tokens_from_monitor: checking monitored_tokens")
        # Create tasks for all tokens
        tasks = [
            self.process_decreasing_token(token_data)
            for _, token_data in monitored_tokens.items()
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    async def process_decreasing_token(self, token_data):
        actual_token_balance = self.wallet_manager.get_token_balance(
            token_data["token_address"]
        )

        potential_trade = PotentialTrade(
            token_data["token_address"],
            token_data["token_name"],
            token_data["pool_address"],
            token_data["fee"],
            token_data["token_base_value"],
        )

        logger.info(
            f"sell_decreasing_tokens_from_monitor: token: {potential_trade.token_address} fee: {potential_trade.fee} pool_address: {potential_trade.pool_address} token_base_value: {potential_trade.token_base_value}"
        )

        trade_data_sell = TradeData(
            trade_type=TradeType.SELL,
            input_amount=actual_token_balance,
            expected_amount=None,
            original_investment_eth=token_data["input_amount"],
        )

        await self.evaluate_decreasing_token(
            potential_trade,
            trade_data_sell,
        )

    async def evaluate_decreasing_token(
        self,
        potential_trade: PotentialTrade,
        trade_data: TradeData,
    ):
        logger.info("evaluate_decreasing_token: start")
        # process the token prices for demo mode
        current_token_amount = await self.protocol_manager.get_min_token_for_native(
            potential_trade.token_address,
            trade_data.original_investment_eth,
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

        # Check if token amount or current_token_amount is negative or invalid
        if trade_data.expected_amount < 0 or current_token_amount < 0:
            # Handle the error or invalid token amount
            logger.error("Invalid token amount. Cannot proceed further.")
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

        await self.token_monitor.update_monitored_token(
            potential_trade,
            {
                "current_roi": float(current_roi_multiplier),
                "expected_roi": float(expected_roi_multiplier),
            },
        )

        has_reached_roi_or_decreased = (
            current_roi_multiplier >= expected_roi_multiplier
        ) or (
            current_roi_multiplier
            < self.token_analysis.data_manager.config["price_decrease_threshold"]
        )

        logger.info(
            f"Selling decreasing tokens: current_price: {current_token_amount}, \
                trade_data.original_investment_eth:{trade_data.original_investment_eth}, current_roi_multiplier: {current_roi_multiplier}, \
                    expected_multiplier:{expected_roi_multiplier} trade_data.expected_amount: {trade_data.expected_amount}"
        )

        if has_reached_roi_or_decreased:
            await self.sell(
                potential_trade,
                trade_data,
                current_roi_multiplier,
                expected_roi_multiplier,
            )

    async def sell(
        self,
        potential_trade,
        trade_data,
        current_roi_multiplier,
        expected_roi_multiplier,
    ):
        # Some code
        await self.trade_controller.trade_decreasing_token(
            potential_trade, trade_data, current_roi_multiplier, expected_roi_multiplier
        )

    async def check_monitored_valid(self, token_address, pool_address):
        if self.demo_mode:
            if not self.wallet_manager.get_demo_mode_tokens().get(token_address):
                logger.info(
                    f"{token_address} is not in the token balance dictionary. \
                        Removing token {token_address} from monitored tokens \
                        ** removed remove_monitored_token **"
                )
                # TODO: FIX REMOVAL OF MONITORED TOKENS
                # await self.token_monitor.remove_monitored_token(
                #     token_address, pool_address
                # )
