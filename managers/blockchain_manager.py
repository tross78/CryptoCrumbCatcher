import json
import logging
import os
from enum import Enum

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware

from models.chain_constants import SelectedChain
from models.dextrade_chain_data import DexTradeChainData

# Get the absolute path to the root of your project
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Construct the absolute path to your .env file
dotenv_path = os.path.join(project_root, ".env")

# Load the .env file
load_dotenv(dotenv_path)


class BlockchainManager:
    def __init__(self, current_chain_num: SelectedChain):
        self.supported_chains = self.get_supported_chains()
        self.erc20_abi = self.load_erc20_abi()
        self.set_current_chain(current_chain_num)
        self.current_native_token_address = self.current_chain.native_token_address
        short_name = self.current_chain.short_name.upper()
        provider_url = os.environ[f"{short_name}_PROVIDER_URL"]
        os.environ["PROVIDER"] = provider_url
        self.web3_instance: Web3 = Web3(Web3.HTTPProvider(provider_url))
        self.web3_instance.middleware_onion.inject(
            geth_poa_middleware, layer=0
        )  # Required for some Ethereum networks

        # Initialize factory contract
        self.wallet_private_key = os.environ["WALLET_PRIVATE_KEY"]
        self.main_account = self.web3_instance.eth.account.from_key(
            self.wallet_private_key
        )
        self.wallet_address = self.main_account.address
        self.gas_limit_per_transaction = 150000  # example gas limit

    def get_wallet_address(self):
        return self.wallet_address

    def get_wallet_private_key(self):
        return self.wallet_private_key

    def get_supported_chains(self):
        supported_chains_data = self.load_supported_chains()

        supported_chains_dict = {
            chain_data["name"]: DexTradeChainData(
                chain_data["name"],
                chain_data["full_name"],
                chain_data["short_name"],
                os.environ.get(f'{chain_data["short_name"].upper()}_PROVIDER_URL'),
                chain_data["subgraph_url"],
                chain_data["subgraph_type"],
                chain_data["factory_address"],
                chain_data["native_token_address"],
            )
            for chain_data in supported_chains_data
        }
        return supported_chains_dict

    def load_supported_chains(self):
        with open("data/supported_chains.json", "r") as json_file:
            return json.load(json_file)

    def load_erc20_abi(self):
        with open("data/erc20_abi.json", "r") as json_file:
            return json.load(json_file)

    def load_dex_contract(self):
        with open("data/uniswap_factory_abi.json", "r") as json_file:
            return json.load(json_file)

    def set_current_chain(self, selected_chain_enum: Enum):
        self.current_chain = self.supported_chains.get(selected_chain_enum.value)
        self.current_native_token_address = self.current_chain.native_token_address

    def get_current_chain(self):
        return self.current_chain

    def get_token_balance(self, wallet_address, token_address):
        token_address = self.web3_instance.to_checksum_address(token_address)
        token_contract = self.web3_instance.eth.contract(
            address=token_address, abi=self.erc20_abi
        )
        return token_contract.functions.balanceOf(wallet_address).call()

    def get_dex_contract(self):
        chain = self.get_current_chain()
        logging.info(f"Current RPC provider URL: {chain.rpc_url}")
        factory_address = chain.factory_address
        factory_contract = self.web3_instance.eth.contract(
            address=factory_address,
            abi=self.load_dex_contract(),
        )
        return factory_contract

    def calculate_gas_cost_wei(self, num_transactions=2):
        gas_limit_per_transaction = self.gas_limit_per_transaction
        gas_price_gwei = self.web3_instance.eth.gas_price
        gas_cost_per_transaction_wei = gas_price_gwei * gas_limit_per_transaction
        total_gas_fees_wei = gas_cost_per_transaction_wei * num_transactions
        return total_gas_fees_wei

    def calculate_gas_cost_eth(self, num_transactions=2):
        gas_limit_per_transaction = self.gas_limit_per_transaction
        gas_price_gwei = self.web3_instance.eth.gas_price
        gas_cost_per_transaction_wei = gas_price_gwei * gas_limit_per_transaction
        total_gas_fees_wei = gas_cost_per_transaction_wei * num_transactions
        total_gas_fees_eth = self.web3_instance.from_wei(total_gas_fees_wei, "ether")
        return total_gas_fees_eth
