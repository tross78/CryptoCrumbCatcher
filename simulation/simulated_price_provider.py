import json
import logging
import time
from decimal import Decimal

from defi.price_provider import PriceProvider
from token_info.token_watchlist import TokenWatchlist


class SimulatedPriceProvider(PriceProvider):
    def __init__(self, dex_client, blockchain_manager):
        super().__init__(dex_client)
        # self.watchlist: TokenWatchlist = TokenWatchlist(5, blockchain_manager)
        self.pump_tokens = []

    def load_data(self):
        with open("simulation/pump_token.json", "r") as json_file:
            self.pump_tokens = json.load(json_file)

    def save_data(self):
        with open("simulation/pump_token.json", "w") as json_file:
            json.dump(self.pump_tokens, json_file)

    # Get token amount of token_trade_amount (ETH) given token token_in
    def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        # self.load_data()
        # Fetch the actual price input using the dex_client
        result = super().get_price_input(token_in, token_out, token_trade_amount, fee)
        # logging.info(f"Simulated get_price_input")
        # for token in self.pump_tokens:
        #     if token["token_address"].lower() == token_in.lower():
        #         increase_basispoints = float(token["increase_basispoints"]) / 10000
        #         increase_percentage = float(increase_basispoints / 100) * float(
        #             token["increase_multiplier"]
        #         )
        #         increased_value = round(result * (1 + (increase_percentage / 100)))
        #         formatted_value = "{:.0f}".format(
        #             increased_value
        #         )  # Remove decimal places
        #         token["increase_multiplier"] = token["increase_multiplier"] + 1
        #         result = int(formatted_value)
        # self.save_data()
        return result

    # # Get amount of token_info for token_trade_amount (ETH)
    # def get_price_output(self, token_in, token_out, token_trade_amount, fee):
    #     self.load_data()
    #     # Fetch the actual price output using the dex_client
    #     result = super().get_price_output(token_in, token_out, token_trade_amount, fee)
    #     logging.info(
    #         f"Simulated get_price_output for token {token_in}: initial token amount for native token: {result} (more means less valuable)"
    #     )
    #     # if self.watchlist.has_token_address(
    #     #     token_in
    #     # ):  # only pump tokens in the watchlist
    #     for token in self.pump_tokens:
    #         if token["token_address"].lower() == token_in.lower():
    #             increase_basispoints = float(token["increase_basispoints"]) / 10000
    #             increase_percentage = float(increase_basispoints / 100) / float(
    #                 token["increase_multiplier"]
    #             )

    #             increased_value = round(result / (1 + (increase_percentage / 100)))
    #             formatted_value = "{:.0f}".format(
    #                 increased_value
    #             )  # Remove decimal places
    #             token["increase_multiplier"] = token["increase_multiplier"] + 1
    #             result = int(formatted_value)
    #     self.save_data()
    #     logging.info(
    #         f"Simulated get_price_output for token {token_in}: new amount for native token: {result} (less means more valuable)"
    #     )
    #     return result

    def calculate_price_increase_percentage(self, start_timestamp, increase_rate):
        current_timestamp = time.time()
        time_difference = current_timestamp - start_timestamp

        # Calculate the number of minutes elapsed
        elapsed_hours = (time_difference / 60) / 60

        # Calculate the price increase based on the elapsed time and increase rate
        # price_increase_percentage = (1 + increase_rate) ** elapsed_minutes
        price_increase_percentage = increase_rate * elapsed_hours
        return price_increase_percentage

    def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        # Fetch the actual price output using the dex_client
        self.load_data()
        result = super().get_price_output(token_in, token_out, token_trade_amount, fee)
        logging.info(
            f"Simulated get_price_output for token {token_in}: initial token amount for native token: {result} (more means less valuable)"
        )

        if result < 0:
            return result

        for token in self.pump_tokens:
            if token["token_address"].lower() == token_in.lower():
                last_checked = token.get("started", 0)
                increase_rate = 0.01 / token["increase_percentage"]
                # Convert increase rate to per minute

                # Adjust the decrease percentage based on the time difference
                decrease_percentage = self.calculate_price_increase_percentage(
                    last_checked, increase_rate
                )

                logging.info(
                    f"Simulated get_price_output adjusted_decrease_percentage {decrease_percentage}"
                )

                decreased_value = round(result * (1 - (decrease_percentage / 100)))
                logging.info(
                    f"Simulated get_price_output decreased value {decreased_value}"
                )
                formatted_value = "{:.0f}".format(decreased_value)
                result = int(formatted_value)

        logging.info(
            f"Simulated get_price_output for token {token_in}: new amount for native token: {result} (less means more valuable)"
        )
        return result
