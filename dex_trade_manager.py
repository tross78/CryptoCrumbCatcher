from web3 import Web3
import os
from web3.middleware import geth_poa_middleware
import requests
from web3.exceptions import ContractLogicError
from os.path import join, dirname
from dotenv import load_dotenv


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
        provider_url="",
        supported_chains=[],
        demo_mode=True,
    ):
        self.demo_mode = True
        os.environ["PROVIDER"] = provider_url
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.w3.middleware_onion.inject(
            geth_poa_middleware, layer=0
        )  # Required for some Ethereum networks
        self.supported_chains = supported_chains

        # Initialize Uniswap client and factory contract
        wallet_private_key = os.environ["WALLET_PRIVATE_KEY"]
        self.main_account = self.w3.eth.account.from_key(
            wallet_private_key)
        wallet_address = self.main_account.address

        self.data_manager = DataManagement(
            supported_chains=supported_chains,
            wallet_address=wallet_address,
            wallet_private_key=wallet_private_key,
            w3=self.w3
        )
        self.data_manager.set_selected_chain(SelectedChain.ETHEREUM_MAINNET)
        self.token_analysis = TokenAnalysis(self.data_manager)
        self.trading = Trading(self.data_manager, self.token_analysis)
