import json
import logging

from web3 import Web3


class DataManagement:
    def __init__(self):
        self.data = {}
        self.config = {}
        with open("config.json", "r") as json_file:
            self.config = json.load(json_file)
        trade_amount_wei = Web3.to_wei(self.config["trade_amount_eth"], "ether")
        self.config["trade_amount_wei"] = trade_amount_wei
