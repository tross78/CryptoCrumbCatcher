from utils import get_percentage_from_string

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import json
import time
import asyncio
from web3 import Web3


class TokenAnalysis():

    MONITOR_TIMEFRAME = 60 * 1  # 1 mins
    PRICE_INCREASE_THRESHOLD = 1 + (0.01 / 100)  # 0.1 price increase
    PRICE_DECREASE_THRESHOLD = PRICE_INCREASE_THRESHOLD * 2
    TOKEN_RATING_THRESHOLD = 50

    def __init__(self, data_manager):
        self.data_manager = data_manager

    def check_token_score(self, token_address):
        # Check if the score is already in the cache
        if token_address in self.data_manager.data['tokensniffer_score_cache']:
            return get_percentage_from_string(self.data_manager.data['tokensniffer_score_cache'][token_address])
        driver = uc.Chrome()
        # Construct the URL for the tokensniffer website
        url = f'https://tokensniffer.com/token/eth/{token_address}'
        driver.get(url)
        time.sleep(10)

        # Extract the HTML content
        html = driver.page_source

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
                self.data_manager.data['tokensniffer_score_cache'][token_address] = score_str
                with open("tokensniffer_cache.json", "w") as json_file:
                    json.dump(
                        self.data_manager.data['tokensniffer_score_cache'], json_file)
                return score
        return 0

    async def is_token_price_increase(self, token_address, pool):
        print(f"Checking price increase for token {token_address}.")
        loop = asyncio.get_event_loop()
        start_price = await loop.run_in_executor(None, self.data_manager.get_native_token_output_price, token_address, 1000000000000000, pool)
        await asyncio.sleep(self.MONITOR_TIMEFRAME)
        end_price = await loop.run_in_executor(None, self.data_manager.get_native_token_output_price, token_address, 1000000000000000, pool)

        threshold_price = int(start_price * self.PRICE_INCREASE_THRESHOLD)
        print(
            f"Token start price: {start_price} Token end price: {end_price} Threshold price: {threshold_price}")

        # Check for errors or no liquidity
        if start_price == -1 or end_price == -1:
            return False, 0

        if end_price >= int(start_price * self.PRICE_INCREASE_THRESHOLD):
            return True, start_price
        return False, start_price

    def get_top_holder_percentage(self, token_address, pool_address):
        checksum_token_address = self.data_manager.w3.to_checksum_address(
            token_address)
        token_contract = self.data_manager.w3.eth.contract(
            address=checksum_token_address, abi=self.data_manager.data['erc20_abi'])
        total_supply = token_contract.functions.totalSupply().call()
        pair_balance = token_contract.functions.balanceOf(pool_address).call()
        top_holder_percentage = (pair_balance / total_supply) * 100
        return top_holder_percentage

    def is_token_distribution_good(self, token_address, holders_threshold, pool_address):
        holders = self.data_manager.get_token_holders(
            token_address, pool_address)
        holders_enough = holders >= holders_threshold
        return holders_enough

    def is_top_holder_percentage_good(self, token_address, top_holder_percentage_threshold, pool_address):
        top_holder_percentage = self.get_top_holder_percentage(
            token_address, pool_address)
        top_holder_percentage_good = top_holder_percentage <= top_holder_percentage_threshold
        return top_holder_percentage_good

    def has_exploits(self, token_address):
        if self.check_token_score(Web3.to_checksum_address(token_address)) >= self.TOKEN_RATING_THRESHOLD:
            return False
        else:
            return True
