import json
import time
from web3 import Web3
import requests
from web3.exceptions import ContractLogicError
import datetime
from uniswap import Uniswap
from requests import RequestException
from token_price_provider import TokenPriceProvider
# from mock_data_provider import MockDataProvider
import logging


class DataManagement:

    def __init__(self, supported_chains=[], wallet_address="", wallet_private_key="", w3="", trade_amount_eth=0.06):
        self.data = {}
        self.load_data()
        self.token_price_provider = TokenPriceProvider(Uniswap(
            address=wallet_address, private_key=wallet_private_key, version=3))
        self.supported_chains = supported_chains
        self.w3 = w3
        self.trade_amount_eth = trade_amount_eth
        self.trade_amount_wei = self.w3.to_wei(trade_amount_eth, 'ether')
        logging.info(f'trade_amount_wei:{self.trade_amount_wei}')

    def set_selected_chain(self, selected_chain_enum):
        self.selected_chain = self.supported_chains.get(
            selected_chain_enum.value)

    def get_selected_chain(self):
        return self.selected_chain

    def load_data(self):
        with open("uniswap_factory_abi.json", "r") as json_file:
            self.data['uniswap_factory_abi'] = json.load(json_file)
        with open("erc20_abi.json", "r") as json_file:
            self.data['erc20_abi'] = json.load(json_file)
        with open("tokensniffer_cache.json", "r") as json_file:
            self.data['tokensniffer_score_cache'] = json.load(json_file)
        # self.data['tokensniffer_score_cache'] = json.loads(
        #     '{"ethereum_mainnet": {}, "arbitrum_mainnet": {}}')
        with open("demo_balance.json", "r") as json_file:
            self.data['demo_balance'] = json.load(json_file)
        with open("monitored_tokens.json", "r") as json_file:
            self.data['monitored_tokens'] = json.load(json_file)

    def get_pool_fee(self, pool):
        first_non_zero_fee = next(
            (fee for fee in pool["fees"] if float(fee["feePercentage"]) > 0), None)
        if first_non_zero_fee:
            return int(float(first_non_zero_fee.get("feePercentage")) * 10000)
        return 0

    # Given token_trade_amount for native_token_address, returns the maximum output amount of token token_address
    def get_max_native_for_token(self, token_address, token_trade_amount, pool):
        token_in = Web3.to_checksum_address(token_address)
        token_out = Web3.to_checksum_address(
            self.get_selected_chain().native_token_address)
        fee = self.get_pool_fee(pool)
        logging.info(
            f'getting price input from dex: token_in { token_in}, token_out: {token_out}, amount_in: {token_trade_amount}, fee {fee}')
        try:

            native_token_amount = self.token_price_provider.get_price_input(
                token_in, token_out, token_trade_amount, fee)
            logging.info(
                f"Native token (WETH) amount for given token amount: {native_token_amount}")
            return native_token_amount
        except Exception as e:
            logging.error(f"Error during price estimation: {e}", exc_info=True)
            return -1

    # Returns the minimum amount of token token_address required to buy token_trade_amount of native_token_address.
    def get_min_token_for_native(self, token_address, token_trade_amount, pool):
        token_in = Web3.to_checksum_address(token_address)
        token_out = Web3.to_checksum_address(
            self.get_selected_chain().native_token_address)
        fee = self.get_pool_fee(pool)
        logging.info(
            f'getting price output from dex: token_in { token_in}, token_out: {token_out}, amount_in: {token_trade_amount}, fee {fee}')
        try:
            # token_price_provider
            native_token_amount = self.token_price_provider.get_price_output(
                token_in, token_out, token_trade_amount, fee)
            return native_token_amount
        except Exception as e:
            logging.error(f"Error during price estimation: {e}", exc_info=True)
            return -1

    def get_token_holders(self, token_address, pool_address):
        # Get the token contract
        checksum_token_address = self.w3.to_checksum_address(
            token_address)
        token_contract = self.w3.eth.contract(
            address=checksum_token_address, abi=self.data['erc20_abi'])

        # Get the total supply of the token
        total_supply = token_contract.functions.totalSupply().call()

        # Get the token balance of the pair contract (liquidity pool)
        pair_balance = token_contract.functions.balanceOf(pool_address).call()

        if pair_balance == 0:
            # Handle the zero balance case, e.g., log a warning or return a default value
            logging.info("Warning: pair_balance is zero. Skipping this token.")
            return 1  # Replace this with a suitable default value
        else:
            holders = total_supply // pair_balance

        return holders

    def get_pools_with_native_token(self, past_time, min_liquidity_usd, min_volume_usd):
        MAX_RETRIES = 3
        RETRY_DELAY = 1  # Delay between retry attempts in seconds
        max_liquidity_usd = 500000
        # query_template = """
        #     {{
        #         pools(first: 1000, orderBy: createdAtTimestamp, orderDirection: desc, where:{{{token_field}: "{native_token_address}", createdAtTimestamp_gte: "{past_time}", totalValueLockedETH_gt: "{min_liquidity_usd}", liquidity_gt: 0, volumeUSD_gt: {min_volume_usd}}}) {{
        #             id
        #             token0 {{
        #                 id
        #                 symbol
        #                 name
        #             }}
        #             token1 {{
        #                 id
        #                 symbol
        #                 name
        #             }}
        #             feeTier
        #             liquidity
        #             sqrtPrice
        #             tick
        #         }}
        #     }}
        # """
#                    createdTimestamp_gte: "{past_time}"
        query_template = """
            {{
                liquidityPools(
                    first: 1000
                    orderBy: createdTimestamp
                    orderDirection: desc
                    where: {{
                    createdTimestamp_gte: "{past_time}"
                    inputTokens_: {{id_contains: "{native_token_address}"}}
                    totalValueLockedUSD_gt: {min_liquidity_usd}
                    totalValueLockedUSD_lt: {max_liquidity_usd}
                    cumulativeVolumeUSD_gt: {min_volume_usd}
                    }}
                ) {{
                    id
                    fees {{
                        id,
                        feePercentage
                    }}
                    tick
                    totalLiquidity
                    inputTokens {{
                        id
                        name
                    }}
                }}
            }}
        """

        queries = [
            query_template.format(native_token_address=self.get_selected_chain().native_token_address, past_time=past_time,
                                  min_liquidity_usd=min_liquidity_usd, max_liquidity_usd=max_liquidity_usd, min_volume_usd=min_volume_usd)
        ]

        all_pools = []
        url = self.get_selected_chain().graph_url

        for query in queries:
            for retry in range(MAX_RETRIES):
                try:
                    response = requests.post(url, json={"query": query})
                    response.raise_for_status()
                    data = response.json()

                    if "data" in data and "liquidityPools" in data["data"]:
                        all_pools.extend(data["data"]["liquidityPools"])
                        break  # Break out of the retry loop if successful
                    else:
                        logging.error(
                            "Unexpected response format from The Graph API.")
                        if retry < MAX_RETRIES - 1:
                            logging.error(
                                f"Retrying in {RETRY_DELAY} seconds...")
                            time.sleep(RETRY_DELAY)
                        else:
                            logging.error("Max retries exceeded. Exiting...")
                            return all_pools

                except (RequestException, ValueError) as e:
                    logging.error(
                        f"Error occurred while calling The Graph API: {e}", exc_info=True)
                    if retry < MAX_RETRIES - 1:
                        logging.error(f"Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                    else:
                        logging.error("Max retries exceeded. Exiting...")
                        return all_pools

        return all_pools

    def get_pool_address(self, factory_contract, token0_address, token1_address, pool):
        try:
            try:
                # Call the contract function that causes the error
                pool_fee = self.get_pool_fee(pool)
                logging.info(
                    f'Getting pool address token0:{token0_address} token1:{token1_address} fee:{pool_fee}')
                return factory_contract.functions.getPool(Web3.to_checksum_address(token0_address), Web3.to_checksum_address(token1_address), pool_fee).call()
            except ContractLogicError:
                logging.info(f"Execution reverted for token: {token1_address}")
                # You can decide to skip the token, retry after some delay, or take any other appropriate action
        except Exception as e:
            logging.error(
                f"Error occurred while getting pair address for token {token1_address}: {e}", exc_info=True)
            raise

    def get_new_tokens(self, factory_contract, past_time_hours=3, min_liquidity_usd=1, min_volume_usd=5000):
        past_time = int((datetime.datetime.now() -
                        datetime.timedelta(hours=past_time_hours)).timestamp())
        pools_with_native_token = self.get_pools_with_native_token(
            past_time, min_liquidity_usd, min_volume_usd)

        new_token_addresses = []
        for pool in pools_with_native_token:
            token0 = pool["inputTokens"][0].get("id")
            token1 = pool["inputTokens"][1].get("id")
            pool_address = self.get_pool_address(
                factory_contract, token0, token1, pool)
            token = token0

            if token.lower() == self.get_selected_chain().native_token_address.lower():
                token = token1
            if token != self.get_selected_chain().native_token_address and pool_address != '0x0000000000000000000000000000000000000000':
                new_token_addresses.append({
                    "token": token,
                    "pool_address": pool_address,
                    "pool": pool
                })
        return list(new_token_addresses)
