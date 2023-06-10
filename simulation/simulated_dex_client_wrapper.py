import asyncio
import datetime
import json
import logging
import time
from datetime import datetime, timedelta

from defi.dex_client_wrapper import DexClientWrapper


class SimulatedDexClientWrapper(DexClientWrapper):
    def __init__(self, dex_client, blockchain_manager):
        super().__init__(dex_client)
        self.lock = asyncio.Lock()  # Add a lock
        self.pump_tokens = []

    async def load_data(self):
        async with self.lock:  # Lock the method
            with open("simulation/pump_token.json", "r") as json_file:
                self.pump_tokens = json.load(json_file)
        logging.info(
            f"Lock released after attempting to load data for SimulatedDexClientWrapper"
        )

    async def save_data(self):
        async with self.lock:  # Lock the method
            with open("simulation/pump_token.json", "w") as json_file:
                json.dump(self.pump_tokens, json_file)
        logging.info(
            f"Lock released after attempting to save data for SimulatedDexClientWrapper"
        )

    # Get token amount of token_trade_amount (ETH) given token token_in
    async def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        # Fetch the actual price input using the dex_client
        await self.load_data()
        result = await super().get_price_input(
            token_in, token_out, token_trade_amount, fee
        )

        for token in self.pump_tokens:
            if token["token_address"].lower() == token_in.lower():
                pump_started = token.get("pump_started", False)

                if pump_started:
                    initial_price = token.get("initial_price")
                    current_price = token.get("current_price", initial_price)
                    multiplier = initial_price / current_price

                    logging.info(f"Simulated get_price_input multiplier {multiplier}")
                    new_value = round(result * multiplier)
                    logging.info(
                        f"Simulated get_price_output decreased value {new_value}"
                    )
                    formatted_value = "{:.0f}".format(new_value)

                    result = int(formatted_value)
        return result

    def calculate_price_increase_percentage(self, start_timestamp, increase_rate):
        current_timestamp = datetime.utcnow().timestamp()  # Convert to Unix timestamp
        time_difference = current_timestamp - start_timestamp
        elapsed_minutes = time_difference / 60
        price_increase_percentage = increase_rate * elapsed_minutes
        return price_increase_percentage

    async def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        # Fetch the actual price output using the dex_client
        await self.load_data()
        result = await super().get_price_output(
            token_in, token_out, token_trade_amount, fee
        )
        logging.info(
            f"Simulated get_price_output for token {token_in}: initial token amount for native token: {result} (more means less valuable)"
        )

        if result < 0:
            return result

        for token in self.pump_tokens:
            if token["token_address"].lower() == token_in.lower():
                pump_started = token.get("pump_started", False)

                if pump_started:
                    initial_price = token.get("initial_price")
                    pumped_at_timestamp = token.get("pumped_at", 0)
                    increase_rate = token["increase_percentage"]

                    price_diff_percent = self.calculate_price_increase_percentage(
                        pumped_at_timestamp, increase_rate
                    )

                    # calculate the new price
                    new_price = initial_price / (1 + price_diff_percent / 100)

                    result = int(new_price)

                    token["current_price"] = result
                else:
                    token["pump_started"] = True
                    token["initial_price"] = int(result)
                    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
                    token["pumped_at"] = five_minutes_ago.timestamp()
                    print(f"Set pumped_at to: {token['pumped_at']}")
        await self.save_data()  # Save the updated pump_tokens data
        logging.info(
            f"Simulated get_price_output for token {token_in}: new amount for native token: {result} (less means more valuable)"
        )
        return result

    def make_trade(self, token_address, native_token_address, trade_amount, fee):
        return

    def make_trade_output(self, token_address, native_token_address, trade_amount):
        return

    def approve(self, token_address, max_approval):
        return
