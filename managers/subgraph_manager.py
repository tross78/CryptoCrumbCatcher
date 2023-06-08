import json
import logging
import os.path
import time
from string import Template
from typing import List

import requests

from managers.blockchain_manager import BlockchainManager
from models.graph_structures import Fee, Pool, Token


class SubgraphManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # Delay between retry attempts in seconds

    def __init__(self, blockchain_manager: BlockchainManager):
        self.blockchain_manager = blockchain_manager
        self.subgraph_parsers = {
            "messari": self.parse_messari,
            "uniswap_v3_eth": self.parse_uniswap_v3,
            "uniswap_v3_goerli": self.parse_uniswap_v3,
            # Add more subgraph types and their corresponding parsing methods
        }

    def read_graphql_file(self, filename):
        with open(filename, "r") as file:
            return file.read()

    def convert_query_to_json(self, query):
        query_lines = query.strip().split("\n")
        query_lines = [line.strip() for line in query_lines]
        query_json = json.dumps(" ".join(query_lines))
        return query_json

    def _send_query(self, query):
        url = self.blockchain_manager.get_current_chain().graph_url
        for retry in range(self.MAX_RETRIES):
            try:
                response = requests.post(url, json={"query": query}, timeout=240)
                response.raise_for_status()
                data = response.json()

                if "data" in data:
                    return data["data"]
                else:
                    logging.error(
                        "Unexpected response format from The Graph API. Data not found"
                    )
                    if retry < self.MAX_RETRIES - 1:
                        logging.error(f"Retrying in {self.RETRY_DELAY} seconds...")
                        time.sleep(self.RETRY_DELAY)
                    else:
                        logging.error("Max retries exceeded. Exiting...")
                        return None

            except (
                requests.RequestException,
                ValueError,
                json.JSONDecodeError,
            ) as error_message:
                logging.error(
                    f"Error occurred while calling The Graph API: {error_message}",
                    exc_info=True,
                )
                if retry < self.MAX_RETRIES - 1:
                    logging.error(f"Retrying in {self.RETRY_DELAY} seconds...")
                    time.sleep(self.RETRY_DELAY)
                else:
                    logging.error("Max retries exceeded. Exiting...")
                    return None

    def parse_subgraph_response(self, subgraph_type, response_data):
        parser = self.subgraph_parsers.get(subgraph_type)
        if parser:
            return parser(response_data)
        else:
            logging.error(f"No parser defined for subgraph type: {subgraph_type}")
            return []

    def parse_uniswap_v3(self, response_data):
        # Parsing logic for Uniswap V3 subgraph

        # Merge poolsWithToken0 and poolsWithToken1
        pools_data = response_data["poolsWithToken0"] + response_data["poolsWithToken1"]

        pools: List[Pool] = []  # Empty list to hold Pool objects

        # Iterating through each pool data dictionary
        for pool_data in pools_data:
            fee = Fee("1", int(float(pool_data["feeTier"])))
            token0 = Token(
                pool_data["token0"]["id"],
                pool_data["token0"]["symbol"],
                pool_data["token0"]["name"],
            )
            token1 = Token(
                pool_data["token1"]["id"],
                pool_data["token0"]["symbol"],
                pool_data["token0"]["name"],
            )
            # Creating Pool object and adding to the list
            pool = Pool(pool_data["id"], token0, token1, fee)
            pools.append(pool)
        return pools

    def to_dict(self, obj):
        if isinstance(obj, list):
            return [self.to_dict(i) for i in obj]
        if not hasattr(obj, "__dict__"):
            return obj
        return {key: self.to_dict(value) for key, value in vars(obj).items()}

    def parse_messari(self, response_data):
        # Parsing logic for Pancake V3 subgraph

        pools_data = response_data["liquidityPools"]  # Your list of pool dictionaries

        pools: List[Pool] = []  # Empty list to hold Pool objects

        # Iterating through each pool data dictionary
        for pool_data in pools_data:
            first_non_zero_fee = next(
                (fee for fee in pool_data["fees"] if float(fee["feePercentage"]) > 0),
                None,
            )
            fee = Fee(
                first_non_zero_fee["id"],
                int(float(first_non_zero_fee.get("feePercentage")) * 10000),
            )

            # Extracting tokens data and transforming into a list of Token objects
            tokens_data = pool_data["inputTokens"]
            tokens = [
                Token(token["id"], token["symbol"], token["name"])
                for token in tokens_data
            ]

            # Creating Pool object and adding to the list
            pool = Pool(pool_data["id"], tokens[0], tokens[1], fee)
            pools.append(pool)
        return pools

    def get_pools_with_native_token(self, past_time, min_liquidity_usd, min_volume_usd):
        max_liquidity_usd = 1000000

        subgraph_type = self.blockchain_manager.get_current_chain().graph_type
        # query_template = self.get_query_template(subgraph_type)

        native_token_address = (
            self.blockchain_manager.get_current_chain().native_token_address.lower()
        )

        if os.path.isfile(f"queries/{subgraph_type}.graphql"):
            query_template = self.read_graphql_file(f"queries/{subgraph_type}.graphql")
        else:
            logging.error(
                f"No query template defined for subgraph type: {subgraph_type}"
            )
            return []

        query_template = Template(query_template)

        query = query_template.substitute(
            native_token_address=native_token_address,
            token0_address=native_token_address,
            token1_address=native_token_address,
            past_time=past_time,
            min_liquidity_usd=min_liquidity_usd,
            max_liquidity_usd=max_liquidity_usd,
            min_volume_usd=min_volume_usd,
        )

        subgraph_response = self._send_query(query)

        parsed_data = self.parse_subgraph_response(subgraph_type, subgraph_response)

        return parsed_data
