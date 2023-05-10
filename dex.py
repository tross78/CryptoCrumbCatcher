from uniswap import Uniswap
from web3 import Web3
from utils import get_percentage_from_string
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import json
import os
from web3.middleware import geth_poa_middleware
import requests
import datetime
from web3.exceptions import ContractLogicError
from os.path import join, dirname
from dotenv import load_dotenv
import asyncio
from collections import deque
from trade_action import TradeAction
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

class DexTradeTools:
    uniswap_client = None
    TOKEN_RATING_THRESHOLD = 100
    MAX_TOKENS_MONITORED = 20
    MONITOR_TIMEFRAME = 60 * 15 # 1 mins
    PRICE_INCREASE_THRESHOLD = 1 + (0.25 / 100)  # 0.25 price increase
    PRICE_DECREASE_THRESHOLD = PRICE_INCREASE_THRESHOLD * 2
    DESIRED_ROI=2 #2x 
    # constructor function    
    def __init__(self, eth_private_key="", infura_key="", demo_mode=True):
        self.demo_mode = True
        # Initialize Ethereum node connection
        infura_key = os.environ['INFURA_KEY']
        infura_url = f'https://mainnet.infura.io/v3/{infura_key}'

        os.environ['PROVIDER'] = infura_url

        self.w3 = Web3(Web3.HTTPProvider(infura_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Required for some Ethereum networks

        self.chains = [
            {
                "name": "Ethereum", 
                "url": f"https://mainnet.infura.io/v3/{infura_key}", 
                "factory_address": "0x1F98431c8aD98523631AE4a59f267346ea31F984"
            },
            # {
            #     "name": "Arbitrum",
            #     "url": "https://arb-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY",
            #     "factory_address": "0xINSERT_ARBITRUM_FACTORY_ADDRESS_HERE",
            #     "subgraph": "https://api.thegraph.com/subgraphs/name/your-arbitrum-subgraph"
            # }
        ]

        # Initialize Uniswap client and factory contract
        self.eth_private_key = os.environ['ETH_PRIVATE_KEY']
        self.main_account = self.w3.eth.account.privateKeyToAccount(eth_private_key)
        self.eth_address = self.main_account.address

        self.uniswap_client = Uniswap(address=self.eth_address, private_key=eth_private_key, version=3)

        self.monitored_token_threads = {}  # Store the token threads in a dictionary

        self.uniswap_factory_abi, self.erc20_abi, self.tokensniffer_score_cache, self.demo_balance, self.monitored_tokens = self.load_data()


    def load_data(self):
        with open("uniswap_factory_abi.json", "r") as json_file:
            uniswap_factory_abi = json.load(json_file)    
        with open("erc20_abi.json", "r") as json_file:
            erc20_abi = json.load(json_file)
        with open("tokensniffer_cache.json", "r") as json_file:
            tokensniffer_score_cache = json.load(json_file)
        with open("demo_balance.json", "r") as json_file:
            demo_balance = json.load(json_file)
        with open("monitored_tokens.json", "r") as json_file:
            monitored_tokens = json.load(json_file)
        return uniswap_factory_abi, erc20_abi, tokensniffer_score_cache, demo_balance, monitored_tokens

    def get_token_eth_output_price(self, token_address, token_trade_amount, pool):
        checksum_token_address = Web3.toChecksumAddress(token_address)
        weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # WETH address on mainnet
        token_in = checksum_token_address
        token_out = weth_address
        fee = int(pool["feeTier"])
        amount_in = token_trade_amount
        # Call the quoteExactInputSingle function to get the token price
        try:
            print(f'getting price from Uniswap: token_in { token_in}, token_out: {token_out}, amount_in: {amount_in}, fee {fee}')
            return self.uniswap_client.get_price_input(token_in, token_out, amount_in, fee)
        except Exception as e:
            print(f"Error during price estimation: {e}")
            return -1

    def get_eth_token_output_price(self, token_address, eth_trade_amount, pool):
        checksum_token_address = Web3.toChecksumAddress(token_address)
        weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # WETH address on mainnet
        token_in = weth_address
        token_out = checksum_token_address
        fee = int(pool["feeTier"])
        amount_in = eth_trade_amount
        # Call the quoteExactInputSingle function to get the token price
        try:
            print(f'getting price from Uniswap: token_in { token_in}, token_out: {token_out}, amount_in: {amount_in}, fee {fee}')
            return self.uniswap_client.get_price_input(token_in, token_out, amount_in, fee) 
        except Exception as e:
            print(f"Error during price estimation: {e}")
            return -1
        
    def check_token_score(self, token_address, tokensniffer_score_cache):
        # Check if the score is already in the cache
        if token_address in tokensniffer_score_cache:
            return get_percentage_from_string(tokensniffer_score_cache[token_address])
        driver = uc.Chrome() 
        # Construct the URL for the tokensniffer website
        url = f'https://tokensniffer.com/token/eth/{token_address}'
        driver.get(url)
        time.sleep(10)

        # Extract the HTML content
        html= driver.page_source

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Close the webdriver
        driver.quit()

        score_elements = soup.select('span[style*="padding-left: 1rem;"]')
        
        score = 0

        for score_element in score_elements:
            score_str = score_element.text.strip()
            if score_element:
                score = get_percentage_from_string(score_str)
                tokensniffer_score_cache[token_address] = score_str
                with open("tokensniffer_cache.json", "w") as json_file:
                    json.dump(tokensniffer_score_cache, json_file)
                return score
        return 0
    
    def get_token_holders(self, token_address, pool_address):
        # Get the token contract
        checksum_token_address = self.w3.toChecksumAddress(token_address)
        token_contract = self.w3.eth.contract(address=checksum_token_address, abi=self.erc20_abi)

        # Get the total supply of the token
        total_supply = token_contract.functions.totalSupply().call()

        # Get the token balance of the pair contract (liquidity pool)
        pair_balance = token_contract.functions.balanceOf(pool_address).call()

        if pair_balance == 0:
            # Handle the zero balance case, e.g., log a warning or return a default value
            print("Warning: pair_balance is zero. Skipping this token.")
            return 1  # Replace this with a suitable default value
        else:
            holders = total_supply // pair_balance

        return holders

    def get_pools_with_weth(self, past_time, min_liquidity_eth, min_volume_usd):
        query_template = """
            {{
                pools(first: 1000, orderBy: createdAtTimestamp, orderDirection: desc, where:{{{token_field}: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", createdAtTimestamp_gte: "{past_time}", totalValueLockedETH_gt: "{min_liquidity_eth}", liquidity_gt: 0, volumeUSD_gt: {min_volume_usd}}}) {{
                    id
                    token0 {{
                        id
                        symbol
                        name
                    }}
                    token1 {{
                        id
                        symbol
                        name
                    }}
                    feeTier
                    liquidity
                    sqrtPrice
                    tick
                }}
            }}
        """
        queries = [
            query_template.format(token_field="token0", past_time=past_time, min_liquidity_eth=min_liquidity_eth, min_volume_usd=min_volume_usd),
            query_template.format(token_field="token1", past_time=past_time, min_liquidity_eth=min_liquidity_eth, min_volume_usd=min_volume_usd)
        ]

        all_pools = []
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        for query in queries:
            response = requests.post(url, json={"query": query})
            data = response.json()
            all_pools.extend(data["data"]["pools"])
        return all_pools


    def get_pool_address(self, factory_contract, token0_address, token1_address, pool):
        try:
            try:
                # Call the contract function that causes the error
                pool_fee = int(pool["feeTier"])
                return factory_contract.functions.getPool(Web3.toChecksumAddress(token0_address), Web3.toChecksumAddress(token1_address), pool_fee).call()
            except ContractLogicError:
                print(f"Execution reverted for token: {token1_address}")
                # You can decide to skip the token, retry after some delay, or take any other appropriate action
        except Exception as e:
            print(f"Error occurred while getting pair address for token {token1_address}: {e}")
            raise

    def get_new_tokens(self, factory_contract, past_time_hours=3, min_liquidity_eth=1, min_volume_usd=5000):
        past_time = int((datetime.datetime.now() - datetime.timedelta(hours=past_time_hours)).timestamp())
        pools_with_weth = self.get_pools_with_weth(past_time, min_liquidity_eth, min_volume_usd)

        new_token_addresses = []
        for pool in pools_with_weth:
            pool_address = self.get_pool_address(factory_contract, pool["token0"]["id"], pool["token1"]["id"], pool)
            token = pool["token0"]["id"]
        
            if token == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":
                token = pool["token1"]["id"]
            if token != "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and pool_address != '0x0000000000000000000000000000000000000000':
                new_token_addresses.append({
                "token": token,
                "pool_address": pool_address,
                "pool": pool
            })
        return list(new_token_addresses)

    # Check if token has a price increase of at least PRICE_INCREASE_THRESHOLD within MONITOR_TIMEFRAME
    async def is_token_price_increase(self, token_address, pool):
        print(f"Checking price increase for token {token_address}.")  # Add this line
        loop = asyncio.get_event_loop()
        start_price = await loop.run_in_executor(None, self.get_token_eth_output_price, token_address, 1000000000000000000, pool)
        await asyncio.sleep(self.MONITOR_TIMEFRAME)
        end_price = await loop.run_in_executor(None, self.get_token_eth_output_price, token_address, 1000000000000000000, pool)

        if end_price >= start_price * self.PRICE_INCREASE_THRESHOLD:
            return True, start_price
        return False, start_price

    def monitor_and_buy_from_watchlist(self, factory_address, weth_address, eth_trade_amount, watchlist):

        watchlist_copy = deque(watchlist)  # Make a copy of the watchlist
        for token in watchlist_copy:
            token_address = token["token_address"]
            if not any(obj["token_address"] == token_address for obj in self.monitored_tokens):
                pool = token["pool"]
                initial_token_price = token["initial_price"]
                current_token_price = self.get_token_eth_output_price(token_address, 1, pool)

                if current_token_price >= initial_token_price * self.PRICE_INCREASE_THRESHOLD:

                    if (self.has_balance_for_trade(token_address, eth_trade_amount, TradeAction.BUY)):
                        if self.demo_mode:
                            self.trade_token_demo(token_address, pool, eth_trade_amount, TradeAction.BUY)
                        else:
                            self.trade_token(token_address, pool, eth_trade_amount)

                        buy_price = token["buy_price"] = current_token_price  # Store the buy price of the token
                        self.add_monitored_token(factory_address, token_address, weth_address, eth_trade_amount, pool, buy_price, initial_token_price)
                    else:
                        print(f"No balance left to trade {token_address}, removing from watchlist.")
                        watchlist.remove(token)

    def monitor_and_sell(self, best_token_price):
        # Sell tokens that reached the desired ROI or have decreased in price by a certain threshold
        for token in self.monitored_tokens:
            token_address = token["token_address"]
            pool = token["pool"]
            buy_price = token.get("buy_price", 0)
            roi = best_token_price / buy_price if buy_price > 0 else 0
            price_decrease_ratio = best_token_price / buy_price if buy_price > 0 else 1

            if roi >= self.DESIRED_ROI or price_decrease_ratio <= self.PRICE_DECREASE_THRESHOLD:
                print(f"Token {token_address} sold due to {'reaching desired ROI' if roi >= self.DESIRED_ROI else 'price decrease'}.")
                if token_address not in self.demo_balance['tokens']:
                    print(f"{token_address} is not in the token balance dictionary. Removing token {token_address} from monitored tokens")
                    self.remove_monitored_token(token_address)
                    return
                token_balance = self.demo_balance['tokens'].get(token_address, 0)
                if (self.has_balance_for_trade(token_address, token_balance, TradeAction.SELL)):
                    self.trade_token_demo(token_address, pool, token_balance, TradeAction.SELL)
                    self.remove_monitored_token(token_address)



    def trade_token(self, token_address, pool, eth_trade_amount):
        try:
            deadline = int(time.time()) + 300  # Set a deadline 5 minutes from now
            #self.uniswap_client.swap_exact_eth_for_tokens(eth_trade_amount, token_address, eth_address, deadline)
            print(f"Traded {Web3.fromWei(eth_trade_amount, 'ether')} ETH for token {token_address}")
        except Exception as e:
            print(f"Error while trading token {token_address}: {e}")

    def get_top_holder_percentage(self, token_address, pool_address):
        checksum_token_address = self.w3.toChecksumAddress(token_address)
        token_contract = self.w3.eth.contract(address=checksum_token_address, abi=self.erc20_abi)
        total_supply = token_contract.functions.totalSupply().call()
        pair_balance = token_contract.functions.balanceOf(pool_address).call()
        top_holder_percentage = (pair_balance / total_supply) * 100
        return top_holder_percentage

    def is_token_distribution_good(self, token_address, holders_threshold, pool_address):
        holders = self.get_token_holders(token_address, pool_address)
        holders_enough = holders >= holders_threshold
        return holders_enough

    def is_top_holder_percentage_good(self, token_address, top_holder_percentage_threshold, pool_address):
        top_holder_percentage = self.get_top_holder_percentage(token_address, pool_address)
        top_holder_percentage_good = top_holder_percentage <= top_holder_percentage_threshold
        return top_holder_percentage_good
    
    def has_balance_for_trade(self, token_address, trade_amount, action):
        estimated_gas_limit = 150000  # You can adjust this based on your experience with Uniswap transactions
        average_gas_price = self.w3.eth.gasPrice  # Get the average gas price in Gwei
        gas_fee = average_gas_price * estimated_gas_limit
        #action_str = "action equals enum BUY or SELL" if action == TradeAction.BUY or TradeAction.SELL else "action not correct format"
        print(f"Token: {token_address}, Trade amount: {trade_amount}, Action: {action}, Gas fee: {gas_fee}")

        if action == TradeAction.BUY:
            if self.demo_balance['eth'] < trade_amount + gas_fee:
                print("Not enough ETH balance to make the trade.")
                return False
            else:
                return True
        if action == TradeAction.SELL:
            if token_address not in self.demo_balance['tokens']:
                print(f"{token_address} is not in the token balance dictionary.")
                return False
            if self.demo_balance['tokens'].get(token_address, 0) < trade_amount:
                print(f"Not enough {token_address} tokens balance to make the trade.")
                return False
            else:
                return True

    def trade_token_demo(self, token_address, pool, trade_amount, action):
        try:
            fee_percentage = int(pool["feeTier"]) / 1000000  # Convert from basis points to a percentage
            average_gas_price = self.w3.eth.gasPrice  # Get the average gas price in Gwei
            estimated_gas_limit = 150000  # You can adjust this based on your experience with Uniswap transactions

            gas_fee = average_gas_price * estimated_gas_limit
            slippage_tolerance = 0.01  # 1% slippage tolerance

            if action == TradeAction.BUY:
                token_amount = self.get_eth_token_output_price(token_address, trade_amount, pool)
                net_token_amount = token_amount * (1 - fee_percentage) * (1 - slippage_tolerance)  # Subtract the fee and consider slippage
                #print(f"Simulated trade: {Web3.fromWei(trade_amount, 'ether')} tokens of {token_address} for {Web3.fromWei(net_eth_amount - gas_fee, 'ether')} ETH")
                self.demo_balance['eth'] -= trade_amount + gas_fee
                self.demo_balance['tokens'][token_address] = self.demo_balance['tokens'].get(token_address, 0) + net_token_amount
                with open("demo_balance.json", "w") as json_file:
                    json.dump(self.demo_balance, json_file)
            elif action == TradeAction.SELL:
                eth_amount = self.get_token_eth_output_price(token_address, trade_amount, pool)
                net_eth_amount = eth_amount * (1 - fee_percentage) * (1 - slippage_tolerance)  # Subtract the fee and consider slippage
                print(f"Simulated trade: {Web3.fromWei(trade_amount, 'ether')} tokens of {token_address} for {Web3.fromWei(net_eth_amount - gas_fee, 'ether')} ETH")
                self.demo_balance['tokens'][token_address] -= trade_amount
                self.demo_balance['eth'] += net_eth_amount - gas_fee
                with open("demo_balance.json", "w") as json_file:
                    json.dump(self.demo_balance, json_file)
            else:
                raise ValueError("Invalid action. Use TradeAction.BUY or TradeAction.SELL.")
        except Exception as e:
            print(f"Error while simulating token trade {token_address}: {e}")

    # def monitor_token_price(self, w3, factory_contract, token_address, base_token_address, pool, eth_trade_amount, threshold, stop_event, monitored_tokens):
    #     try:
    #         checksummed_token_address = w3.toChecksumAddress(token_address)
    #         pool_address = self.get_pool_address(factory_contract, pool["token0"]["id"], pool["token1"]["id"], pool)
    #         token_contract = w3.eth.contract(address=checksummed_token_address, abi=self.erc20_abi)
    #         base_token_contract = w3.eth.contract(address=base_token_address, abi=self.erc20_abi)

    #         # Get the initial token price
    #         initial_token_balance = token_contract.functions.balanceOf(pool_address).call()
    #         initial_base_token_balance = base_token_contract.functions.balanceOf(pool_address).call()
    #         initial_token_price = initial_base_token_balance / initial_token_balance

    #         while True:
    #             token_balance = token_contract.functions.balanceOf(pool_address).call()
    #             base_token_balance = base_token_contract.functions.balanceOf(pool_address).call()
    #             token_price = base_token_balance / token_balance

    #             # Compare the current token price with the initial price multiplied by the threshold
    #             if token_price >= initial_token_price * threshold:
    #                 self.trade_token_demo(token_address, pool, eth_trade_amount, TradeAction.SELL)
    #                 stop_event.set()
    #                 # Remove the object with the matching "token" element
    #                 monitored_tokens = [obj for obj in monitored_tokens if obj["token"] != token_address]
    #             # Check if the stop_event is set and exit the loop if it is
    #             if stop_event.is_set():
    #                 return

    #             time.sleep(60)  # Check the price every minute.
    #     except Exception as e:
    #         print(f"Error occurred while monitoring token {token_address} and pair {pool_address}: {e}")
    #         raise

    def add_monitored_token(self, factory_address, token_address, weth_address, eth_trade_amount, pool, buy_price, initial_price):
        if token_address not in self.monitored_tokens:
            self.monitored_tokens.append({
                "token_address": token_address,
                "factory_address": factory_address,
                "weth_address": weth_address,
                "eth_trade_amount": eth_trade_amount,
                "pool": pool,
                "buy_price": buy_price,
                "initial_price": initial_price
            })
            print(f"Token {token_address} added to monitored tokens.")
        else:
            print(f"Token {token_address} is already in monitored tokens.")


    def remove_monitored_token(self, token_address):
        # Remove the object with the matching "token" element
        self.monitored_tokens = [obj for obj in self.monitored_tokens if obj["token_address"] != token_address]

        # Stop the monitoring thread for the token
        if token_address in self.monitored_token_threads:
            thread, stop_event = self.monitored_token_threads[token_address]
            stop_event.set()  # Signal the monitoring thread to stop
            thread.join()  # Wait for the thread to finish
            del self.monitored_token_threads[token_address]  # Remove the thread from the dictionary

        # Save the updated list of monitored tokens
        with open("monitored_tokens.json", "w") as json_file:
            json.dump(self.monitored_tokens, json_file)

    def get_best_token_price(self, watchlist):
        # Get the highest valued token from watchlist
        best_token_price = 0
        for token in watchlist:
            token_address = token["token_address"]
            pool = token["pool"]
            token_price = self.get_token_eth_output_price(token_address, 1, pool)
            if token_price > best_token_price:
                best_token_price = token_price
        return best_token_price


    def has_exploits(self, token_address):
        if self.check_token_score(Web3.toChecksumAddress(token_address), self.tokensniffer_score_cache) >= self.TOKEN_RATING_THRESHOLD:
            return False
        else:
            return True