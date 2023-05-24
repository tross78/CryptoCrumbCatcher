from web3 import Web3
import os
from web3.middleware import geth_poa_middleware
import requests
from web3.exceptions import ContractLogicError
from os.path import join, dirname
from dotenv import load_dotenv
from dextrade_chain_data import DexTradeChainData


from trade_action import TradeAction
from chain_constants import SelectedChain
from data_management import DataManagement
from token_analysis import TokenAnalysis
from trading import Trading

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)


class DexTradeManager:

    MAX_TOKENS_MONITORED = 5

    def __init__(
        self,
        wallet_private_key="",
        supported_chains=[],
        trade_amount_eth=0.06,
        selected_chain=SelectedChain.ETHEREUM_MAINNET,
        demo_mode=True,
    ):
        self.demo_mode = True
        chain_data = supported_chains.get(selected_chain.value)
        short_name = chain_data.short_name.upper()
        provider_url = os.environ[f'{short_name}_PROVIDER_URL']
        os.environ["PROVIDER"] = provider_url
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.w3.middleware_onion.inject(
            geth_poa_middleware, layer=0
        )  # Required for some Ethereum networks
        self.supported_chains = supported_chains

        # Initialize factory contract
        wallet_private_key = os.environ["WALLET_PRIVATE_KEY"]
        self.main_account = self.w3.eth.account.from_key(
            wallet_private_key)
        wallet_address = self.main_account.address

        self.data_manager = DataManagement(
            supported_chains=supported_chains,
            wallet_address=wallet_address,
            wallet_private_key=wallet_private_key,
            w3=self.w3,
            trade_amount_eth=trade_amount_eth
        )
        self.data_manager.set_selected_chain(selected_chain)
        self.token_analysis = TokenAnalysis(self.data_manager)
        self.trading = Trading(self.data_manager, self.token_analysis)
