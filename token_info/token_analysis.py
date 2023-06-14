import asyncio
import json
import logging
import time
from decimal import Decimal

import aiofiles
import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from web3 import Web3

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.wallet_manager import WalletManager
from utils import get_percentage_from_string


class TokenAnalysis:
    def __init__(
        self,
        data_manager,
        blockchain_manager,
        protocol_manager,
        wallet_manager: WalletManager,
    ):
        self.data_manager: DataManagement = data_manager
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.protocol_manager: ProtocolManager = protocol_manager
        self.token_score_cache = {}
        self.lock = asyncio.Lock()  # Add a lock
        self.wallet_manager = wallet_manager
        # self.load_token_score_cache()

    async def load_token_score_cache(self):
        if self.data_manager.config["enable_tokensniffer_scraping"]:
            await self.load_token_score_cache_local()
        else:
            await self.load_token_score_cache_remote()

    async def load_token_score_cache_remote(self):
        response = requests.get(
            "https://raw.githubusercontent.com/tross78/CryptoCrumbCatcher/main/data/tokensniffer_cache.json",
            timeout=30,
        )
        self.token_score_cache = json.loads(response.text)

    async def load_token_score_cache_local(self):
        try:
            async with aiofiles.open("data/tokensniffer_cache.json", "r") as json_file:
                self.token_score_cache = json.loads(await json_file.read())
        except (FileNotFoundError, json.JSONDecodeError):
            # File does not exist or invalid JSON. Initialize an empty dict.
            self.token_score_cache = {}

    def get_token_score_from_cache(self, token_address):
        selected_chain = self.blockchain_manager.get_current_chain()

        # Using get() method to avoid nested if conditions
        cache = self.token_score_cache.get(selected_chain.name, {}).get(
            token_address, {}
        )

        # Check if cache is not empty
        if cache:
            cached_score = cache.get("score", 0)
            last_checked = cache.get("last_checked", 0)

            # Calculate the time difference
            current_timestamp = time.time()
            time_difference = current_timestamp - last_checked

            # Handle 'pending' or '-1' score case here
            if cached_score == -1 and time_difference > 86400:  # More than 24 hours
                logging.info(
                    "More than 24 hours have passed since the last check for pending score. \
                        Getting fresh score."
                )
                return False
            elif cached_score not in [-1]:
                # logging.info(f'Token score found in cache: {cached_score}')
                return cached_score
            else:
                logging.info("Token score is pending")
                return -1

        return False

    async def check_token_score(self, token_address):
        token_score = self.get_token_score_from_cache(token_address)
        if token_score is not False:
            return token_score
        enable_tokensniffer_scraping = self.data_manager.config[
            "enable_tokensniffer_scraping"
        ]
        if enable_tokensniffer_scraping:
            token_score = await self.scrape_tokensniffer_score(token_address)
            return token_score

        return 0

    async def scrape_tokensniffer_score(self, token_address):
        selected_chain = self.blockchain_manager.get_current_chain()
        short_name = selected_chain.short_name

        options = uc.ChromeOptions()
        # options.add_argument("--headless")
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")

        driver = uc.Chrome(options=options)
        url = f"https://tokensniffer.com/token/{short_name}/{token_address}"
        driver.get(url)

        # Wait for the page to load (adjust the delay if needed)
        time.sleep(30)

        if self.is_cloudflare_challenge(driver):
            logging.info(
                "Cloudflare challenge encountered. Completing the challenge..."
            )
            complete_challenge = self.complete_cloudflare_challenge(driver)
            if complete_challenge:
                logging.info("cloudflare challenge completed")
            # Wait for the page to reload after completing
            # the challenge (adjust the delay if needed)
            time.sleep(30)

        html = driver.page_source

        # Wait for the page to load (adjust the delay if needed)
        time.sleep(120)

        html = driver.page_source

        score = self.extract_score_from_html(html)
        await self.cache_token_score(token_address, score)
        driver.quit()
        # logging.info(f'token retrieved from tokensniffer: {score}')
        return score

    def is_cloudflare_challenge(self, driver):
        iframe_elements = driver.find_elements(
            By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"
        )
        checkbox_elements = driver.find_elements(
            By.CSS_SELECTOR, "input[name='cf-turnstile-response']"
        )

        return bool(iframe_elements and checkbox_elements)

    def complete_cloudflare_challenge(self, driver):
        iframe = driver.find_element(
            By.CSS_SELECTOR, "iframe[src^='https://challenges.cloudflare.com']"
        )

        # define the end points for the curve relative to the iframe's top left corner
        end_x, end_y = 40, 40  # adjust these as necessary

        # get the absolute position of the end point
        end_x_abs = iframe.location["x"] + end_x
        end_y_abs = iframe.location["y"] + end_y

        # switch to the iframe
        driver.switch_to.frame(iframe)

        # get the current mouse position
        # start_x, start_y = pyautogui.position()  # replace with actual method

        # # Move the mouse with pyautogui
        # steps = 100
        # step_x = (end_x_abs - start_x) / steps
        # step_y = (end_y_abs - start_y) / steps
        # for i in range(steps):
        #     pyautogui.moveTo(start_x + i * step_x, start_y + i * step_y, duration=0.01)
        #     time.sleep(0.01)  # adjust delay for smoother motion

        # switch back to the default_content
        driver.switch_to.default_content()

        # prepare action chains
        actions = ActionChains(driver)

        # perform the final click
        actions.move_to_element_with_offset(iframe, end_x, end_y)
        actions.click().perform()
        return True

    def extract_score_from_html(self, html):
        soup = BeautifulSoup(html, "html.parser")
        score_elements = soup.select('span[style*="padding-left: 1rem;"]')

        for score_element in score_elements:
            score_str = score_element.text.strip()
            score = get_percentage_from_string(score_str)
            if score > 0:
                return score

        token_pending = soup.find("div", class_="Home_section__16Giz")
        if token_pending and token_pending.text.strip() == "Token is pending review":
            logging.info("token pending review: returning -1")
            return -1

        # logging.info("token score not found: returning 0")
        return 0  # No non-zero scores found

    async def cache_token_score(self, token_address, score):
        selected_chain = self.blockchain_manager.get_current_chain()
        current_timestamp = time.time()
        token_data = self.token_score_cache.setdefault(
            selected_chain.name, {}
        ).setdefault(token_address, {})

        token_data["score"] = score
        token_data["last_checked"] = current_timestamp

        async with self.lock:  # Lock the method
            async with aiofiles.open("data/tokensniffer_cache.json", "w") as json_file:
                await json_file.write(json.dumps(self.token_score_cache))
        logging.info(
            f"Lock released after attempting to load data for cache_token_score"
        )

    async def is_token_price_increase(self, token_address, fee, pool_address):
        trade_amount = int(
            self.wallet_manager.get_native_token_balance_percentage(
                self.data_manager.config["trade_amount_percentage"]
            )
        )
        try:
            print("starting is_token_price_increase start_amount")
            start_amount = await self.protocol_manager.get_min_token_for_native(
                token_address,
                trade_amount,
                fee,
            )

            await asyncio.sleep(self.data_manager.config["monitor_timeframe"])

            print("starting is_token_price_increase end_amount")
            end_amount = await self.protocol_manager.get_min_token_for_native(
                token_address,
                trade_amount,
                fee,
            )

            if start_amount == -1 or end_amount == -1:
                return False, 0

            price_increase_threshold = self.data_manager.config[
                "price_increase_threshold"
            ]

            threshold_amount = int(
                Decimal(str(start_amount)) / Decimal(str(price_increase_threshold))
            )

            print(
                f"Token start amount: {start_amount} \
                Token end amount: {end_amount} \
                    Threshold amount: {threshold_amount}"
            )

            if end_amount < threshold_amount:
                return True, start_amount

            return False, start_amount

        except Exception as e:
            logging.error(f"Error in is_token_price_increase: {e}")
            print(f"Error in is_token_price_increase: {e}")
            return False, 0

    # def get_top_holder_percentage(self, token_address, pool_address):
    #     checksum_token_address = self.blockchain_manager.web3_instance.to_checksum_address(
    #         token_address)
    #     token_contract = self.blockchain_manager.web3_instance.eth.contract(
    #         address=checksum_token_address, abi=self.data_manager.data['erc20_abi'])
    #     total_supply = token_contract.functions.totalSupply().call()
    #     pair_balance = token_contract.functions.balanceOf(pool_address).call()
    #     top_holder_percentage = (pair_balance / total_supply) * 100
    #     return top_holder_percentage

    # def is_token_distribution_good(self, token_address, holders_threshold, pool_address):
    #     holders = self.data_manager.get_token_holders(
    #         token_address, pool_address)
    #     holders_enough = holders >= holders_threshold
    #     return holders_enough

    # def is_top_holder_percentage_good(self,
    #  token_address, top_holder_percentage_threshold,
    # pool_address):
    #     top_holder_percentage = self.get_top_holder_percentage(
    #         token_address, pool_address)
    #     top_holder_percentage_good = top_holder_percentage <= top_holder_percentage_threshold
    #     return top_holder_percentage_good

    async def has_exploits(self, token_address):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        if current_chain_name != "goerli_testnet":
            token_score = await self.check_token_score(
                Web3.to_checksum_address(token_address)
            )
            if token_score >= self.data_manager.config["token_rating_threshold"]:
                return False
            else:
                return True
        return False
