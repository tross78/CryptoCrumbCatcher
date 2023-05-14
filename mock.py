import random
import time


class MockPriceInput:

    WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    def __init__(self, increase_duration=10, decrease_duration=10, min_price_increase_percentage=0.2, price_decrease_percentage=0.3):
        self.call_count = 0
        self.increase_duration = increase_duration
        self.decrease_duration = decrease_duration
        self.min_price_increase_percentage = min_price_increase_percentage
        self.price_decrease_percentage = price_decrease_percentage

        self.exchange_rate = 0.000000000931324  # AMT in 1 ETH
        self.start_time = time.time()

    def mock_get_price_input(self, token_in, token_out, amount_in, fee):
        # Calculate the elapsed time in minutes
        elapsed_time = (time.time() - self.start_time) / 60

        #amount_in = float(amount_in) / float(10 ** 18)

        if token_in.lower() == self.WETH_ADDRESS.lower():
            output = float(amount_in) * float(self.exchange_rate)
        else:
            output = float(amount_in) / float(self.exchange_rate)

        # Increase the price for a specified duration
        if elapsed_time < self.increase_duration:
            increase_percentage = max(self.min_price_increase_percentage, random.uniform(self.min_price_increase_percentage, self.min_price_increase_percentage * 4))
            output *= (1 + increase_percentage)

        # Decrease the price after the increase_duration has passed
        elif elapsed_time >= self.increase_duration and elapsed_time < (self.increase_duration + self.decrease_duration):
            output *= (1 - self.price_decrease_percentage)

        # Reset the start_time and start the cycle again
        else:
            self.start_time = time.time()

        return int(output * (10 ** 18))

