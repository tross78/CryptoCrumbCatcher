import asyncio
import json
import time

import aiofiles
import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from logger_config import logger
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.vpn_server_manager import VPNServerManager
from utils import get_percentage_from_string


class TokensnifferScraper:
    def __init__(
        self, data_manager: DataManagement, blockchain_manager: BlockchainManager
    ):
        self.vpn_manager = VPNServerManager()
        self.data_manager: DataManagement = data_manager
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.token_score_cache = None
        self.lock = asyncio.Lock()  # Add a lock

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

    async def get_token_score_from_cache(self, token_address):
        if not self.token_score_cache:
            self.token_score_cache = {}
            await self.load_token_score_cache()
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
            if (
                cached_score < 0 and time_difference > 86400
            ) or cached_score == -2:  # More than 24 hours
                logger.info(
                    "More than 24 hours have passed since the last check for pending score. \
                        Or, there was an error getting the score. Getting fresh score."
                )

                del self.token_score_cache[selected_chain.name][token_address]
                return False
            elif cached_score not in [-1]:
                # logger.info(f'Token score found in cache: {cached_score}')
                return cached_score
            else:
                logger.info("Token score is pending")
                return -1

        return False

    async def scrape_tokensniffer_score(self, token_address):
        self.vpn_manager.connect_to_server()
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
            logger.info("Cloudflare challenge encountered. Completing the challenge...")
            complete_challenge = self.complete_cloudflare_challenge(driver)
            if complete_challenge:
                logger.info("cloudflare challenge completed")
            # Wait for the page to reload after completing
            # the challenge (adjust the delay if needed)
            time.sleep(30)

        html = driver.page_source

        # Wait for the page to load (adjust the delay if needed)
        time.sleep(120)

        html = driver.page_source

        score = self.extract_score_from_html(html)
        await self.cache_token_score(token_address, score)
        self.vpn_manager.disconnect_from_server()
        driver.quit()
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

        # switch to the iframe
        driver.switch_to.frame(iframe)

        # switch back to the default_content
        driver.switch_to.default_content()

        # prepare action chains
        actions = ActionChains(driver)

        # perform the final click
        actions.move_to_element_with_offset(iframe, end_x, end_y)
        actions.click().perform()
        return True
        # ...

    def extract_score_from_html(self, html):
        soup = BeautifulSoup(html, "html.parser")
        score_elements = soup.select('span[style*="padding-left: 1rem;"]')

        for score_element in score_elements:
            score_str = score_element.text.strip()
            score = get_percentage_from_string(score_str)
            return score

        token_pending = soup.find("div", class_="Home_section__16Giz")
        if token_pending and token_pending.text.strip() == "Token is pending review":
            logger.info("token pending review: returning -1")
            return -1

        return -2  # No non-zero scores found

    async def cache_token_score(self, token_address, score):
        if not self.token_score_cache:
            self.token_score_cache = {}
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
        logger.info(
            f"Lock released after attempting to load data for cache_token_score"
        )

    async def check_token_score(self, token_address):
        token_score = await self.get_token_score_from_cache(token_address)
        if token_score is not False:
            return token_score
        enable_tokensniffer_scraping = self.data_manager.config[
            "enable_tokensniffer_scraping"
        ]
        if enable_tokensniffer_scraping:
            token_score = await self.scrape_tokensniffer_score(token_address)
            return token_score

        return 0
