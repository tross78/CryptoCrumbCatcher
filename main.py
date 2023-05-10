import time
from web3 import Web3
from web3.exceptions import ContractLogicError
from collections import deque
from dex import DexTradeTools
import os
import asyncio
from trade_action import TradeAction
async def main():
    #global demo_mode
    #demo_mode = True  # Set to False for real trading

    eth_price_usd = 1840

    tvl_eth = 5  # Set the desired TVL ETH
    liquidity_pct = 0.2  # Set the desired liquidity as a percentage of TVL
    volume_pct = 0.02  # Set the desired volume as a percentage of TVL

    # Calculate the equivalent values for liquidity and volume
    min_liquidity_eth = tvl_eth * liquidity_pct
    min_volume_usd = tvl_eth * volume_pct * eth_price_usd * 24  # Assuming a 24-hour period and using the current ETH price in USD

    max_created_threshold = 72

    holders_threshold = 50
    top_holder_percentage = 10
    eth_trade_amount = Web3.toWei(0.001, 'ether')
    weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # WETH address on mainnet

    dextools = DexTradeTools(os.environ['ETH_PRIVATE_KEY'], os.environ['INFURA_KEY'], demo_mode=True)

    watchlist = deque(maxlen=dextools.MAX_TOKENS_MONITORED)


    # for obj in monitored_tokens:
    #     add_monitored_token(obj["factory_address"], obj["token"], weth_address, eth_trade_amount, obj["pool"])
    tasks = []  # Initialize the list of tasks
    while True:
        #for chain in dextools.chains:
        # Update the connection and contract 
        chain = dextools.chains[0]
        url = chain['url']
        w3 = Web3(Web3.HTTPProvider(url))
        print(f"Current RPC provider URL: {url}")
        factory_address = chain["factory_address"]

        # Initialize Uniswap/PancakeSwap factory contract
        factory_contract = w3.eth.contract(address=factory_address, abi=dextools.uniswap_factory_abi)
        new_tokens = dextools.get_new_tokens(factory_contract, max_created_threshold, min_liquidity_eth, min_volume_usd)

        # Keep track of tokens with pending tasks
        tokens_with_tasks = set()

        for obj in new_tokens:
            token_address = obj["token"]
            pool_address = obj["pool_address"]
            pool = obj["pool"]

            if token_address in dextools.monitored_tokens:
                print(f"Token {token_address} is already being monitored.")
                continue

            if (dextools.is_token_distribution_good(token_address, holders_threshold, pool_address) and
                    dextools.is_top_holder_percentage_good(token_address, top_holder_percentage, pool_address) and
                    not dextools.has_exploits(token_address) and
                    token_address not in tokens_with_tasks):

                # Create a task for is_token_price_increase
                task = asyncio.create_task(dextools.is_token_price_increase(token_address, pool))
                tasks.append((task, token_address, pool))
                tokens_with_tasks.add(token_address)
                print(f"Created task for token {token_address}.")
        # Run tasks concurrently using asyncio.gather()
        results = await asyncio.gather(*[task for task, _, _ in tasks])

        # Update watchlist based on the results
        for i, result in enumerate(results):
            if result:
                _, token_address, pool = tasks[i]
                if not any(obj["token_address"] == token_address for obj in watchlist):
                    watchlist.append({"token_address": token_address, "pool": pool, "initial_price": result[1]})
                    print(f"Token {token_address} added to watchlist.")
        # Remove completed tasks and tokens from the lists
        for task_info in tasks.copy():
            task, token_address, pool = task_info
            if task.done():
                tasks.remove(task_info)
                tokens_with_tasks.remove(token_address)
                if task.result():
                    if not any(obj["token_address"] == token_address for obj in watchlist):
                        watchlist.append({"token_address": token_address, "pool": pool, "initial_price": result[1]})
                        print(f"Token {token_address} added to watchlist.")

        best_token_price = dextools.get_best_token_price(watchlist)

        # Monitor the watchlist and buy tokens that meet the performance criteria
        dextools.monitor_and_buy_from_watchlist(factory_address, weth_address, eth_trade_amount, watchlist)
        # Iterate the monitored tokens and sell underperforming tokens
        dextools.monitor_and_sell(best_token_price)
        time.sleep(60)  # Check for new tokens every minute

if __name__ == '__main__':
    asyncio.run(main())