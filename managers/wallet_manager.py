import asyncio
import json

import aiofiles
from web3 import Web3

from logger_config import logger
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement


class WalletManager:
    def __init__(
        self,
        blockchain_manager: BlockchainManager,
        data_manager: DataManagement,
        demo_mode=True,
        reset_userdata_on_load=True,
    ):
        self.wallet_address = blockchain_manager.get_wallet_address()
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.data_manager: DataManagement = data_manager
        self.demo_mode = demo_mode
        self.demo_balances = self.load_demo_balances(reset_userdata_on_load)
        self.lock = asyncio.Lock()  # Add a lock

    def get_native_token_balance_percentage(self, percentage):
        balance = self.get_token_balance(
            self.blockchain_manager.current_native_token_address.lower()
        )
        return int(balance * percentage)

    def get_demo_mode_tokens(self):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        return self.demo_balances[current_chain_name]["tokens"]

    def get_token_balance(self, token_address):
        token_address = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        if self.demo_mode:
            current_chain_name = self.blockchain_manager.get_current_chain().name

            balance = self.demo_balances[current_chain_name]["tokens"].get(
                token_address.lower(), 0
            )
            return balance
        else:
            balance = self.blockchain_manager.get_token_balance(
                self.wallet_address, token_address
            )
            return balance

    def get_native_token_balance(self):
        balance = self.get_token_balance(
            self.blockchain_manager.current_native_token_address.lower()
        )
        return balance

    async def update_native_value_total(self, native_value):
        async with self.lock:  # Lock the method
            selected_chain = self.blockchain_manager.get_current_chain()
            current_native_value = self.demo_balances[selected_chain.name].get(
                "total_native_value", 0
            )
            self.demo_balances[selected_chain.name]["total_native_value"] = (
                current_native_value + native_value
            )
            await self.save_demo_balances(self.demo_balances)

    async def set_native_value_total(self, native_value):
        async with self.lock:  # Lock the method
            selected_chain = self.blockchain_manager.get_current_chain()
            self.demo_balances[selected_chain.name]["total_native_value"] = native_value
            await self.save_demo_balances(self.demo_balances)

    async def set_native_token_balance(self, token_amount):
        async with self.lock:  # Lock the method
            selected_chain = self.blockchain_manager.get_current_chain()
            self.demo_balances[selected_chain.name]["tokens"][
                self.blockchain_manager.current_native_token_address.lower()
            ] = token_amount
            await self.save_demo_balances(self.demo_balances)

    async def set_token_balance(self, token_address, balance):
        async with self.lock:  # Lock the method
            if self.demo_mode:
                current_chain_name = self.blockchain_manager.get_current_chain().name
                self.demo_balances[current_chain_name]["tokens"][
                    token_address.lower()
                ] = balance
                if balance == 0:
                    del self.demo_balances[current_chain_name]["tokens"][
                        token_address.lower()
                    ]
                await self.save_demo_balances(self.demo_balances)
            else:
                raise Exception("Can't manually set balance in non-demo mode")

    def load_demo_balances(self, start_fresh):
        if start_fresh:
            data = {
                "ethereum_mainnet": {
                    "tokens": {
                        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": 1000000000000000000
                    }
                },
                "arbitrum_mainnet": {
                    "tokens": {
                        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": 1000000000000000000
                    }
                },
                "bsc_mainnet": {
                    "tokens": {
                        "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": 1000000000000000000
                    }
                },
            }
            with open("data/demo_balance.json", "w") as json_file:
                json.dump(data, json_file)
        with open("data/demo_balance.json", "r") as json_file:
            return json.load(json_file)

    async def save_demo_balances(self, demo_balances):
        async with aiofiles.open("data/demo_balance.json", "w") as json_file:
            await json_file.write(json.dumps(demo_balances))
