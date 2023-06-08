# chain_constants.py
from enum import Enum


class SelectedChain(Enum):
    ETHEREUM_MAINNET = "ethereum_mainnet"
    ARBITRUM_MAINNET = "arbitrum_mainnet"
    BSC_MAINNET = "bsc_mainnet"
    GOERLI_TESTNET = "goerli_testnet"
    # Add more chains as needed
