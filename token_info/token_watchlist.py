"""
A class used to manage a watchlist of tokens.
"""
import asyncio
import json

import aiofiles

from logger_config import logger
from managers.blockchain_manager import BlockchainManager


class TokenWatchlist:
    def __init__(self, max_tokens, blockchain_manager: BlockchainManager):
        self.tokens = {}
        self.max_tokens = max_tokens
        self.blockchain_manager = blockchain_manager
        self.lock = asyncio.Lock()  # Add a lock
        # self.load_from_file()

    def __iter__(self):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        for token in self.tokens.get(current_chain_name, {}):
            yield self.tokens[current_chain_name][token]

    def __len__(self):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        return len(self.tokens.get(current_chain_name, {}))

    async def update(self, tasks_with_infos):
        logger.info(
            f"Updating watchlist with {len(tasks_with_infos)} tasks. Current watchlist token count: {len(self)}"
        )

        for task_info in tasks_with_infos:
            task, token_address, fee, pool_address = task_info
            try:
                result = task.result()  # Get the result from the already completed task
            except Exception as error_message:
                logger.error(
                    f"Error while running task: {error_message}. Task info: {task_info}"
                )
                continue

            if result:
                try:
                    if not self.is_duplicate(token_address, pool_address):
                        (price_has_increased, token_base_value) = result
                        print(
                            f"price_has_increased: {price_has_increased} token_base_value: {token_base_value}"
                        )
                        if price_has_increased:
                            await self.add(
                                token_address, fee, pool_address, token_base_value
                            )
                except Exception as error_message:
                    logger.error(
                        f"Error while processing task result: {error_message}. Task info: {task_info}"
                    )
                    continue

    async def add(self, token_address, fee, pool_address, token_base_value):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        if len(self.tokens.get(current_chain_name, {})) < self.max_tokens:
            current_chain_name = self.blockchain_manager.get_current_chain().name

            if (
                not self.is_duplicate(token_address, pool_address)
                and len(self.tokens.get(current_chain_name, {})) < self.max_tokens
                and token_base_value > 0  # weeds out errored price calls
            ):
                token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
                if current_chain_name not in self.tokens:
                    self.tokens[current_chain_name] = {}
                    # add token dict
                self.tokens[current_chain_name][token_pool_id] = {
                    "token_address": token_address.lower(),
                    "fee": fee,
                    "pool_address": pool_address.lower(),
                    "token_base_value": token_base_value,
                }

                logger.info(f"Token {token_address} added to watchlist.")
                await self.save_to_file()

    async def remove(self, token_address, pool_address):
        try:
            current_chain_name = self.blockchain_manager.get_current_chain().name
            token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"

            if (
                current_chain_name in self.tokens
                and token_pool_id in self.tokens[current_chain_name]
            ):
                logger.info(f"Deleting Token {token_address} from watchlist")
                del self.tokens[current_chain_name][token_pool_id]
                await self.save_to_file()
            else:
                logger.info(
                    f"Token {token_address} not found in the watchlist for the {current_chain_name} chain."
                )
        except Exception as e:
            logger.error(
                f"Exception occurred in remove method: {str(e)}", exc_info=True
            )

    def is_duplicate(self, token_address, pool_address):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
        return token_pool_id in self.tokens.get(current_chain_name, {})

    def has_token_address(self, token_address):
        current_chain_name = self.blockchain_manager.get_current_chain().name

        for token_data in self.tokens.get(current_chain_name, {}).values():
            if token_data["token_address"] == token_address:
                return True

        return False

    async def load_from_file(self):
        try:
            async with aiofiles.open("data/watchlist.json", "r") as json_file:
                self.tokens = json.loads(await json_file.read())
                logger.info("watchlist loaded from file")
        except (FileNotFoundError, json.JSONDecodeError):
            # File does not exist or invalid JSON. Initialize an empty dict.
            self.tokens = {}

    async def save_to_file(self):
        async with self.lock:  # Lock the method
            async with aiofiles.open("data/watchlist.json", "w") as json_file:
                await json_file.write(json.dumps(self.tokens))
            logger.info("Lock released after attempting to save_to_file on watchlist")
