from enum import IntEnum
import time
import os
import asyncio
from web3 import Web3
from collections import deque
from dex_trade_manager import DexTradeManager
from dextrade_chain_data import DexTradeChainData
from mock_data_provider import MockPriceInput

import unittest
from token_analysis import TokenAnalysis
from trading import Trading

ETH_PRICE_USD = 1840
TVL_ETH = 1
LIQUIDITY_PCT = 0.2
VOLUME_PCT = 0.02
MAX_CREATED_THRESHOLD = 72
HOLDERS_THRESHOLD = 30
TOP_HOLDER_PERCENTAGE = 10
trade_amount_eth = Web3.to_wei(0.06, 'ether')
SUPPORTED_CHAINS = [
    DexTradeChainData("ethereum_mainnet", "Ethereum Mainnet", f"{os.environ['PROVIDER_URL']}", "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
                      "0x1F98431c8aD98523631AE4a59f267346ea31F984", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    DexTradeChainData("bsc_mainnet", "Binance Smart Chain Mainnet", "https://bsc-dataseed.binance.org",
                      "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange", "0x...", ""),
]


def initialize_dex_trade_manager():
    return DexTradeManager(os.environ['WALLET_PRIVATE_KEY'], os.environ['PROVIDER_URL'], SUPPORTED_CHAINS, demo_mode=True)


def update_connection_and_contract(dex_trade_manager):
    chain = dex_trade_manager.data_manager.get_selected_chain()
    w3 = Web3(Web3.HTTPProvider(chain.rpc_url))
    factory_address = chain.factory_address
    factory_contract = w3.eth.contract(
        address=factory_address, abi=dex_trade_manager.data_manager.data['uniswap_factory_abi'])
    return factory_contract, w3


class TestTokenAnalysis(unittest.TestCase):
    def setUp(self):
        self.dex_trade_manager: DexTradeManager = initialize_dex_trade_manager()
        self.data_manager = self.dex_trade_manager.data_manager
        self.token_analysis = TokenAnalysis(self.data_manager)
        self.trading = Trading(self.data_manager, self.token_analysis)

    def test_get_min_token_for_native(self):
        token_address = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
        pool = {"id": "0x11950d141ecb863f01007add7d1a342041227b58", "token0": {"id": "0x6982508145454ce325ddbe47a25d4ec3d2311933", "symbol": "PEPE", "name": "Pepe"}, "token1": {"id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                                                                                                                                                                                 "symbol": "WETH", "name": "Wrapped Ether"}, "feeTier": "3000", "liquidity": "437145219362590512755060153", "sqrtPrice": "2520890257830475310536376", "tick": "-207120", "totalValueLockedETH": "7427.307661119117070739410325900035"}

        price = self.token_analysis.data_manager.get_min_token_for_native(
            token_address, 1000000000000000, pool)

        # Replace the condition below with a condition that makes sense for your test case
        # For example, check if the price is within a certain range or not equal to -1
        self.assertTrue(price > 0, "Price should be greater than zero")

    def test_get_best_token_price(self):
        watchlist = [
            {
                "token_address": "0x6982508145454ce325ddbe47a25d4ec3d2311933",
                "pool":  {"id": "0x11950d141ecb863f01007add7d1a342041227b58", "token0": {"id": "0x6982508145454ce325ddbe47a25d4ec3d2311933", "symbol": "PEPE", "name": "Pepe"}, "token1": {"id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "symbol": "WETH", "name": "Wrapped Ether"}, "feeTier": "3000", "liquidity": "437145219362590512755060153", "sqrtPrice": "2520890257830475310536376", "tick": "-207120", "totalValueLockedETH": "7427.307661119117070739410325900035"}
            },
            {
                "token_address": "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce",
                "pool": {"id": "0x94e4b2e24523cf9b3e631a6943c346df9687c723", "token0": {"id": "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce", "symbol": "SHIB", "name": "SHIBA INU"}, "token1": {"id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "symbol": "WETH", "name": "Wrapped Ether"}, "feeTier": "500", "liquidity": "32391504326547460469621", "sqrtPrice": "5515203516269559754754687", "tick": "-191462", "totalValueLockedETH": "15.42104195281033874132796872875379"},
            },
        ]
        # Get the best token price using the real get_min_token_for_native
        best_token_price, best_token = self.trading.get_best_token_price(
            watchlist)
        # Assert the expected best token price and token address
        assert best_token["token_address"] == "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce"


if __name__ == '__main__':
    unittest.main()
