import json
import logging

from web3 import Web3

from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement

logging.basicConfig(
    filename="trade.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


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

    def get_demo_mode_tokens(self):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        return self.demo_balances[current_chain_name]["tokens"]

    def get_token_balance(self, token_address):
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

    def set_native_token_balance(self, token_amount):
        selected_chain = self.blockchain_manager.get_current_chain()
        self.demo_balances[selected_chain.name]["tokens"][
            self.blockchain_manager.current_native_token_address.lower()
        ] = token_amount

    def set_token_balance(self, token_address, balance):
        if self.demo_mode:
            current_chain_name = self.blockchain_manager.get_current_chain().name
            self.demo_balances[current_chain_name]["tokens"][
                token_address.lower()
            ] = balance
            if balance == 0:
                del self.demo_balances[current_chain_name]["tokens"][
                    token_address.lower()
                ]
            self.save_demo_balances(self.demo_balances)
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
            self.save_demo_balances(data)

        with open("data/demo_balance.json", "r") as json_file:
            return json.load(json_file)

    def save_demo_balances(self, demo_balances):
        with open("data/demo_balance.json", "w") as json_file:
            json.dump(demo_balances, json_file)
