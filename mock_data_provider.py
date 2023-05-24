import random
from typing import Union, Optional, List

Address = str
ChecksumAddress = str

class MockDataProvider:
    def __init__(self, initial_price_range=(928694010, 39700000000000), increase_probability=0.5, increase_range=(1.5, 2)):
        self.prices = {}  # Prices for tokens
        self.initial_price_range = initial_price_range
        self.increase_probability = increase_probability  # Probability of a token price increase
        self.increase_range = increase_range  # Range of increase factors for token prices

    def get_initial_price(self):
        return random.randint(*self.initial_price_range)

    def simulate_price_increase(self, token: Union[Address, ChecksumAddress]):
        # Always increase the price by a factor within the increase range
        increase_factor = random.uniform(*self.increase_range)
        self.prices[token] = round(self.prices[token] / increase_factor)

    def get_price_input(self, token_in: Union[Address, ChecksumAddress], token_out: Union[Address, ChecksumAddress], qty: int, fee: Optional[int] = None, route: Optional[List[Union[Address, ChecksumAddress]]] = None) -> int:
        if token_in not in self.prices:
            self.prices[token_in] = self.get_initial_price()
        self.simulate_price_increase(token_in)  # Increase price of DAI
        if token_out not in self.prices:
            self.prices[token_out] = self.get_initial_price()
        return int(qty * self.prices[token_in] / self.prices[token_out])

    def get_price_output(self, token_in: Union[Address, ChecksumAddress], token_out: Union[Address, ChecksumAddress], qty: int, fee: Optional[int] = None, route: Optional[List[Union[Address, ChecksumAddress]]] = None) -> int:
        if token_in not in self.prices:
            self.prices[token_in] = self.get_initial_price()
        self.simulate_price_increase(token_in)  # Increase price of DAI
        if token_out not in self.prices:
            self.prices[token_out] = self.get_initial_price()
        return int(qty * self.prices[token_out] / self.prices[token_in])
