import logging
from utils import get_percentage_from_string

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import json
import time
import asyncio
from web3 import Web3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import random
import numpy as np
import pyautogui


class TokenAnalysis():

    MONITOR_TIMEFRAME = 60 * 15  # 1 mins
    PRICE_INCREASE_THRESHOLD = 1 + (0.25 / 100)  # 1% price increase
    PRICE_DECREASE_THRESHOLD = 0.9
    TOKEN_RATING_THRESHOLD = 70

    def __init__(self, data_manager):
        self.data_manager = data_manager

    def check_token_score(self, token_address):
        selected_chain = self.data_manager.get_selected_chain()
        logging.info(f'getting token score for : {token_address}')
        if token_address in self.data_manager.data['tokensniffer_score_cache'][selected_chain.name]:
            cached_score = get_percentage_from_string(
                self.data_manager.data['tokensniffer_score_cache'][selected_chain.name][token_address])
            logging.info(f'token score found in cache: {cached_score}')
            return cached_score

        logging.info(f'getting token score from tokensniffer')
        short_name = selected_chain.short_name
        driver = uc.Chrome()
        url = f'https://tokensniffer.com/token/{short_name}/{token_address}'
        driver.get(url)

        # Wait for the page to load (adjust the delay if needed)
        time.sleep(30)

        if self.is_cloudflare_challenge(driver):
            logging.info(
                "Cloudflare challenge encountered. Completing the challenge...")
            complete_challenge = self.complete_cloudflare_challenge(driver)
            if (complete_challenge):
                logging.info(f'cloudflare challenge completed')
            # Wait for the page to reload after completing the challenge (adjust the delay if needed)
            time.sleep(30)

        html = driver.page_source

        # Wait for the page to load (adjust the delay if needed)
        time.sleep(120)

        html = driver.page_source

        score = self.extract_score_from_html(html)
        if score > -1:  # don't cache if token is pending, check later
            self.cache_token_score(token_address, score)
        driver.quit()
        logging.info(f'token retrieved from tokensniffer: {score}')
        return score

    def is_cloudflare_challenge(self, driver):
        iframe_elements = driver.find_elements(
            By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
        checkbox_elements = driver.find_elements(
            By.CSS_SELECTOR, "input[name='cf-turnstile-response']")

        if iframe_elements and checkbox_elements:
            return True
        else:
            return False

    def bezier_curve(self, x1, y1, x2, y2, n=30):
        t = np.linspace(0, 1, n)
        curve_points = [(int((1 - ti) * x1 + ti * x2),
                        int((1 - ti) * y1 + ti * y2)) for ti in t]
        return curve_points

    def complete_cloudflare_challenge(self, driver):
        iframe = driver.find_element(
            By.CSS_SELECTOR, "iframe[src^='https://challenges.cloudflare.com']")

        # define the end points for the curve relative to the iframe's top left corner
        end_x, end_y = 40, 40  # adjust these as necessary

        # get the absolute position of the end point
        end_x_abs = iframe.location['x'] + end_x
        end_y_abs = iframe.location['y'] + end_y

        # switch to the iframe
        driver.switch_to.frame(iframe)

        # get the current mouse position
        start_x, start_y = pyautogui.position()  # replace with actual method

        # Move the mouse with pyautogui
        steps = 100
        step_x = (end_x_abs - start_x) / steps
        step_y = (end_y_abs - start_y) / steps
        for i in range(steps):
            pyautogui.moveTo(start_x + i * step_x, start_y +
                             i * step_y, duration=0.01)
            time.sleep(0.01)  # adjust delay for smoother motion

        # switch back to the default_content
        driver.switch_to.default_content()

        # prepare action chains
        actions = ActionChains(driver)

        # perform the final click
        actions.move_to_element_with_offset(iframe, end_x, end_y)
        actions.click().perform()
        return True

    def extract_score_from_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        score_elements = soup.select('span[style*="padding-left: 1rem;"]')

        for score_element in score_elements:
            score_str = score_element.text.strip()
            score = get_percentage_from_string(score_str)
            if score > 0:
                return score

        token_pending = soup.find('div', class_='Home_section__16Giz')
        if token_pending and token_pending.text.strip() == "Token is pending review":
            logging.info("token pending review: returning -1")
            return -1

        logging.info("token score not found: returning 0")
        return 0  # No non-zero scores found

    def cache_token_score(self, token_address, score):
        selected_chain = self.data_manager.get_selected_chain()
        self.data_manager.data['tokensniffer_score_cache'][selected_chain.name][token_address] = score
        with open("tokensniffer_cache.json", "w") as json_file:
            json.dump(
                self.data_manager.data['tokensniffer_score_cache'], json_file)

    async def is_token_price_increase(self, token_address, pool):
        logging.info(f"Checking price increase for token {token_address}.")
        loop = asyncio.get_event_loop()

        start_price = await loop.run_in_executor(None, self.data_manager.get_min_token_for_native, token_address, self.data_manager.trade_amount_wei, pool)
        await asyncio.sleep(self.MONITOR_TIMEFRAME)
        end_price = await loop.run_in_executor(None, self.data_manager.get_min_token_for_native, token_address, self.data_manager.trade_amount_wei, pool)

        threshold_price = int(start_price * self.PRICE_INCREASE_THRESHOLD)
        logging.info(
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
        token_score = self.check_token_score(
            Web3.to_checksum_address(token_address))
        if token_score >= self.TOKEN_RATING_THRESHOLD:
            return False
        else:
            return True
