import json

from web3 import Web3

from logger_config import logger


class DataManagement:
    def __init__(self):
        self.data = {}
        self.config = {}
        with open("config.json", "r") as json_file:
            self.config = json.load(json_file)
