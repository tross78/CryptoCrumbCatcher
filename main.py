from enum import IntEnum
import time
import os
import asyncio
from web3 import Web3
from collections import deque
from chain_constants import SelectedChain
from dex_trade_manager import DexTradeManager
from dextrade_chain_data import DexTradeChainData
import json
import logging
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

ETH_PRICE_USD = 1823
LIQUIDITY_USD = 50000
MAX_CREATED_THRESHOLD = 168
HOLDERS_THRESHOLD = 20
TOP_HOLDER_PERCENTAGE = 10
trade_amount_eth = 0.06


def get_select_chain_input(selected_chain_options):
    while True:
        print("Available chain options:")
        for i, option in enumerate(selected_chain_options, start=1):
            print(f"{i}. {option.value}")

        user_input = input(
            "Enter the number corresponding to your selected chain: ")

        try:
            option_index = int(user_input) - 1
            if 0 <= option_index < len(selected_chain_options):
                selected_chain = selected_chain_options[option_index]
                return selected_chain
        except ValueError:
            pass

        print("Invalid input. Please try again.")


def get_supported_chains():
    with open('supported_chains.json', 'r') as f:
        supported_chains_data = json.load(f)

    supported_chains_dict = {chain_data["name"]: DexTradeChainData(
        chain_data["name"],
        chain_data["full_name"],
        chain_data["short_name"],
        os.environ.get(f'{chain_data["short_name"].upper()}_PROVIDER_URL'),
        chain_data["subgraph_url"],
        chain_data["factory_address"],
        chain_data["native_token_address"]
    )
        for chain_data in supported_chains_data}
    return supported_chains_dict


async def main(user_selected_chain):
    dex_trade_manager: DexTradeManager = initialize_dex_trade_manager(
        user_selected_chain)
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


def initialize_dex_trade_manager(user_selected_chain):
    return DexTradeManager(os.environ['WALLET_PRIVATE_KEY'], get_supported_chains(), trade_amount_eth, user_selected_chain, demo_mode=True)


def update_connection_and_contract(dex_trade_manager):
    chain = dex_trade_manager.data_manager.get_selected_chain()
    w3 = Web3(Web3.HTTPProvider(chain.rpc_url))
    logging.info(f"Current RPC provider URL: {chain.rpc_url}")
    factory_address = chain.factory_address
    factory_contract = w3.eth.contract(
        address=factory_address, abi=dex_trade_manager.data_manager.data['uniswap_factory_abi'])
    return factory_contract, w3


def get_new_tokens(dex_trade_manager, factory_contract):

    # Set the ratio
    tvl_to_volume_ratio = 4  # Example ratio

    # Calculate Volume
    min_volume_usd = int(LIQUIDITY_USD / tvl_to_volume_ratio)

    return dex_trade_manager.data_manager.get_new_tokens(factory_contract, MAX_CREATED_THRESHOLD, LIQUIDITY_USD, min_volume_usd)


def create_tasks_for_new_tokens(dex_trade_manager, new_tokens):
    tasks = []
    tokens_with_tasks = set()
    for token_info in new_tokens:
        token_address = token_info["token"]
        pool_address = token_info["pool_address"]
        pool = token_info["pool"]

        if token_address in dex_trade_manager.data_manager.data['monitored_tokens']:
            logging.info(f"Token {token_address} is already being monitored.")
            continue

        # if (dex_trade_manager.token_analysis.is_token_distribution_good(token_address, HOLDERS_THRESHOLD, pool_address) and
        #         dex_trade_manager.token_analysis.is_top_holder_percentage_good(token_address, TOP_HOLDER_PERCENTAGE, pool_address) and
        #         not dex_trade_manager.token_analysis.has_exploits(token_address) and
        #         token_address not in tokens_with_tasks):
        if (not dex_trade_manager.token_analysis.has_exploits(token_address) and token_address not in tokens_with_tasks):

            task = asyncio.create_task(
                dex_trade_manager.token_analysis.is_token_price_increase(token_address, pool))
            tasks.append((task, token_address, pool))
            tokens_with_tasks.add(token_address)
            logging.info(f"Created task for token {token_address}.")

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
        logging.info(f"Token {token_address} added to watchlist.")


def monitor_and_trade_tokens(dex_trade_manager, factory_contract, watchlist):
    dex_trade_manager.trading.monitor_and_buy_from_watchlist(
        factory_contract.address, dex_trade_manager.data_manager.get_selected_chain().native_token_address, trade_amount_eth, watchlist)
    dex_trade_manager.trading.monitor_and_sell()


user_selected_chain = get_select_chain_input(list(SelectedChain))
print(f"Selected chain: {user_selected_chain.value}")

if __name__ == '__main__':
    asyncio.run(main(user_selected_chain))
