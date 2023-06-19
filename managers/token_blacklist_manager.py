import asyncio
import json

import aiofiles

from logger_config import logger
from managers.blockchain_manager import BlockchainManager


class TokenBlacklistManager:
    def __init__(self, blockchain_manager: BlockchainManager):
        self.tokens = None
        self.blockchain_manager = blockchain_manager
        self.lock = asyncio.Lock()  # Add a lock

    async def add_to_blacklist(self, token_address):
        if not self.tokens:
            await self.load_from_file()
        current_chain_name = self.blockchain_manager.get_current_chain().name
        chain_tokens = self.tokens.get(current_chain_name, [])
        token_address_lower = token_address.lower()

        for i, token in enumerate(chain_tokens):
            if token.get("token_address") == token_address_lower:
                token["retries"] += 1  # increment retries count
                chain_tokens[i] = token  # update the token in the list
                break
        else:  # this else corresponds to the for loop (it executes when the loop completes without a break)
            chain_tokens.append({"token_address": token_address_lower, "retries": 1})

        self.tokens[
            current_chain_name
        ] = chain_tokens  # update your original dictionary
        await self.save_to_file()

    async def remove_from_blacklist(self, token_address):
        if not self.tokens:
            await self.load_from_file()
        current_chain_name = self.blockchain_manager.get_current_chain().name
        chain_tokens = self.tokens.get(current_chain_name, [])
        token_address_lower = token_address.lower()

        for i, token in enumerate(chain_tokens):
            if token.get("token_address") == token_address_lower:
                del chain_tokens[i]
                break

        self.tokens[current_chain_name] = chain_tokens
        await self.save_to_file()

    async def is_token_blacklisted(self, token_address):
        if not self.tokens:
            await self.load_from_file()
        current_chain_name = self.blockchain_manager.get_current_chain().name
        chain_tokens = self.tokens.get(current_chain_name, [])
        token_address_lower = token_address.lower()

        for token in chain_tokens:
            if (
                token.get("token_address") == token_address_lower
                and token.get("retries") > 5
            ):
                return True
        return False

    async def load_from_file(self):
        try:
            async with self.lock:  # Lock the method
                async with aiofiles.open("data/token_blacklist.json", "r") as json_file:
                    self.tokens = json.loads(await json_file.read())
                    logger.info("blacklist loaded from file")
        except (FileNotFoundError, json.JSONDecodeError):
            # File does not exist or invalid JSON. Initialize an empty dict.
            self.tokens = {}

    async def save_to_file(self):
        async with self.lock:  # Lock the method
            async with aiofiles.open("data/token_blacklist.json", "w") as json_file:
                await json_file.write(json.dumps(self.tokens))
            logger.info("Lock released after attempting to save_to_file on blacklist")
