from enum import IntEnum
import time
import os
import asyncio
from web3 import Web3
from collections import deque
from dex_trade_manager import DexTradeManager
from dextrade_chain_data import DexTradeChainData
from mock import MockPriceInput

ETH_PRICE_USD = 1840
TVL_ETH = 1
LIQUIDITY_PCT = 0.2
VOLUME_PCT = 0.02
MAX_CREATED_THRESHOLD = 72
HOLDERS_THRESHOLD = 30
TOP_HOLDER_PERCENTAGE = 10
ETH_TRADE_AMOUNT = Web3.to_wei(0.001, 'ether')
SUPPORTED_CHAINS = [
    DexTradeChainData("ethereum_mainnet", "Ethereum Mainnet", f"{os.environ['PROVIDER_URL']}", "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
                      "0x1F98431c8aD98523631AE4a59f267346ea31F984", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    DexTradeChainData("bsc_mainnet", "Binance Smart Chain Mainnet", "https://bsc-dataseed.binance.org",
                      "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange", "0x...", ""),
]


async def main():
    dex_trade_manager: DexTradeManager = initialize_dex_trade_manager()
    mock_price_input = MockPriceInput()
    dex_trade_manager.data_manager.uniswap_client.get_price_input = mock_price_input.mock_get_price_input
    watchlist = deque(maxlen=dex_trade_manager.MAX_TOKENS_MONITORED)

    while True:
        factory_contract, w3 = update_connection_and_contract(
            dex_trade_manager)
        new_tokens = get_new_tokens(dex_trade_manager, factory_contract)
        tasks, tokens_with_tasks = create_tasks_for_new_tokens(
            dex_trade_manager, new_tokens)
        await update_watchlist(tasks, tokens_with_tasks, watchlist, dex_trade_manager)
        monitor_and_trade_tokens(
            dex_trade_manager, factory_contract, watchlist)
        time.sleep(60)


def initialize_dex_trade_manager():
    return DexTradeManager(os.environ['WALLET_PRIVATE_KEY'], os.environ['PROVIDER_URL'], SUPPORTED_CHAINS, demo_mode=True)


def update_connection_and_contract(dex_trade_manager):
    chain = dex_trade_manager.data_manager.get_selected_chain()
    w3 = Web3(Web3.HTTPProvider(chain.rpc_url))
    print(f"Current RPC provider URL: {chain.rpc_url}")
    factory_address = chain.factory_address
    factory_contract = w3.eth.contract(
        address=factory_address, abi=dex_trade_manager.data_manager.data['uniswap_factory_abi'])
    return factory_contract, w3


def get_new_tokens(dex_trade_manager, factory_contract):
    min_liquidity_eth = TVL_ETH * LIQUIDITY_PCT
    min_volume_usd = TVL_ETH * VOLUME_PCT * ETH_PRICE_USD * 24
    return dex_trade_manager.data_manager.get_new_tokens(factory_contract, MAX_CREATED_THRESHOLD, min_liquidity_eth, min_volume_usd)


def create_tasks_for_new_tokens(dex_trade_manager, new_tokens):
    tasks = []
    tokens_with_tasks = set()
    for token_info in new_tokens:
        token_address = token_info["token"]
        pool_address = token_info["pool_address"]
        pool = token_info["pool"]

        if token_address in dex_trade_manager.data_manager.data['monitored_tokens']:
            print(f"Token {token_address} is already being monitored.")
            continue

        # if (dex_trade_manager.token_analysis.is_token_distribution_good(token_address, HOLDERS_THRESHOLD, pool_address) and
        #         dex_trade_manager.token_analysis.is_top_holder_percentage_good(token_address, TOP_HOLDER_PERCENTAGE, pool_address) and
        #         not dex_trade_manager.token_analysis.has_exploits(token_address) and
        #         token_address not in tokens_with_tasks):
        if (token_address not in tokens_with_tasks):

            task = asyncio.create_task(
                dex_trade_manager.token_analysis.is_token_price_increase(token_address, pool))
            tasks.append((task, token_address, pool))
            tokens_with_tasks.add(token_address)
            print(f"Created task for token {token_address}.")

    return tasks, tokens_with_tasks


async def update_watchlist(tasks, tokens_with_tasks, watchlist, dex_trade_manager):
    tasks_copy = tasks.copy()
    results = await asyncio.gather(*[task for task, _, _ in tasks_copy])

    for i, result in enumerate(results):
        if result:
            _, token_address, pool = tasks_copy[i]
            if not any(obj["token_address"] == token_address for obj in watchlist):
                (price_increase, initial_price) = result
                add_token_to_watchlist(
                    token_address, pool, initial_price, watchlist)

    completed_tasks = [task_info[0]
                       for task_info in tasks if task_info[0].done()]

    for task in completed_tasks:
        completed_task_info = None
        for task_info in tasks:
            if task_info[0] == task:
                completed_task_info = task_info
                break
        if completed_task_info is not None:
            completed_task, token_address, pool = completed_task_info
            tasks.remove(completed_task_info)
            tokens_with_tasks.remove(token_address)
            (price_increase, initial_price) = completed_task.result()
            if not any(obj["token_address"] == token_address for obj in watchlist) and price_increase:
                add_token_to_watchlist(
                    token_address, pool, initial_price, watchlist)


def add_token_to_watchlist(token_address, pool, initial_price, watchlist):
    if not any(obj["token_address"] == token_address for obj in watchlist):
        watchlist.append({"token_address": token_address,
                         "pool": pool, "initial_price": initial_price})
        print(f"Token {token_address} added to watchlist.")


def monitor_and_trade_tokens(dex_trade_manager, factory_contract, watchlist):
    best_token_price = dex_trade_manager.trading.get_best_token_price(
        watchlist)
    dex_trade_manager.trading.monitor_and_buy_from_watchlist(
        factory_contract.address, dex_trade_manager.data_manager.get_selected_chain().native_token_address, ETH_TRADE_AMOUNT, watchlist)
    dex_trade_manager.trading.monitor_and_sell(best_token_price)


if __name__ == '__main__':
    asyncio.run(main())
