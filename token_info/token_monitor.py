import asyncio
import json

import aiofiles

from logger_config import logger
from managers.wallet_manager import WalletManager
from models.trade_data import PotentialTrade, TradeData


class TokenMonitor:
    def __init__(
        self, selected_chain_name, wallet_manager: WalletManager, reset_userdata_on_load
    ):
        self.reset_userdata_on_load = reset_userdata_on_load
        self.tokens = {}
        self.selected_chain_name = selected_chain_name
        self.wallet_manager = wallet_manager
        self.lock = asyncio.Lock()  # Add a lock

    def get_monitored_tokens(self):
        return self.tokens.setdefault(self.selected_chain_name, {})

    def set_monitored_tokens(self, monitored_tokens):
        self.tokens[self.selected_chain_name] = monitored_tokens
        self.save_monitored_tokens()

    async def load_monitored_tokens(self):
        try:
            async with self.lock:  # Lock the method
                async with aiofiles.open(
                    "data/monitored_tokens.json", "r"
                ) as json_file:
                    self.tokens = json.loads(await json_file.read())
                    logger.info(f"Monitored tokens loaded {self.tokens}")
        except (FileNotFoundError, json.JSONDecodeError):
            # File does not exist or invalid JSON. Initialize an empty dict.
            logger.info("Monitored tokens not loaded")
            self.tokens = {}

    async def save_monitored_tokens(self):
        async with self.lock:  # Lock the method
            async with aiofiles.open("data/monitored_tokens.json", "w") as json_file:
                await json_file.write(json.dumps(self.tokens))
                logger.info(
                    "Lock released after attempting to save_to_file on token_monitor"
                )

    def is_duplicate(self, token_address, pool_address):
        token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
        monitored_tokens = self.get_monitored_tokens()
        return any(
            f'{obj["token_address"]}_{obj["pool_address"]}' == token_pool_id
            for obj in monitored_tokens.values()
        )

    def has_token_address(self, token_address):
        for token_data in self.tokens.get(self.selected_chain_name, {}).values():
            if token_data["token_address"] == token_address:
                return True

        return False

    async def add_monitored_token(
        self,
        potential_trade: PotentialTrade,
        trade_data: TradeData,
    ):
        monitored_tokens = self.get_monitored_tokens()
        if not self.is_duplicate(
            potential_trade.token_address, potential_trade.pool_address
        ):
            token_pool_id = (
                f"{potential_trade.token_address}_{potential_trade.pool_address}"
            )

            # update the token balance due to slippage, fees, etc
            actual_token_balance = self.wallet_manager.get_token_balance(
                potential_trade.token_address.lower()
            )
            monitored_tokens[token_pool_id] = {
                "token_address": potential_trade.token_address.lower(),
                "fee": potential_trade.fee,
                "pool_address": potential_trade.pool_address.lower(),
                "token_base_value": potential_trade.token_base_value,
                "input_amount": trade_data.input_amount,
            }
            logger.info(
                f"Token {potential_trade.token_address} added to monitored tokens."
            )
            # Save the updated dictionary of monitored tokens
            await self.save_monitored_tokens()
        else:
            logger.info(
                f"Token {potential_trade.token_address} is already in monitored tokens."
            )

    async def remove_monitored_token(self, token_address, pool_address):
        # Remove the object with the matching "token_address" and "pool_address" combination
        monitored_tokens = self.get_monitored_tokens()
        removed_tokens = [
            key
            for key, obj in monitored_tokens.items()
            if obj["token_address"] == token_address
            and obj["pool_address"] == pool_address
        ]
        for token_key in removed_tokens:
            del monitored_tokens[token_key]

        # Save the updated dictionary of monitored tokens
        await self.save_monitored_tokens()
