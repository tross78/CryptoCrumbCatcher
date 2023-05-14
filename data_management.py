import json
from web3 import Web3
import requests
from web3.exceptions import ContractLogicError
import datetime
from uniswap import Uniswap


class DataManagement:

    def __init__(self, supported_chains=[], wallet_address="", wallet_private_key="", w3=""):
        self.data = {}
        self.load_data()
        self.uniswap_client = Uniswap(
            address=wallet_address, private_key=wallet_private_key, version=3)
        self.supported_chains = supported_chains
        self.w3 = w3

    def set_selected_chain(self, selected_chain_enum):
        self.selected_chain = next(
            chain for chain in self.supported_chains if chain.name == selected_chain_enum.value)

    def get_selected_chain(self):
        return self.selected_chain

    def load_data(self):
        with open("uniswap_factory_abi.json", "r") as json_file:
            self.data['uniswap_factory_abi'] = json.load(json_file)
        with open("erc20_abi.json", "r") as json_file:
            self.data['erc20_abi'] = json.load(json_file)
        with open("tokensniffer_cache.json", "r") as json_file:
            self.data['tokensniffer_score_cache'] = json.load(json_file)
        with open("demo_balance.json", "r") as json_file:
            self.data['demo_balance'] = json.load(json_file)
        with open("monitored_tokens.json", "r") as json_file:
            self.data['monitored_tokens'] = json.load(json_file)

    def get_token_native_output_price(self, token_address, native_token_trade_amount, pool):
        # checksum_token_address = Web3.to_checksum_address()
        token_out = Web3.to_checksum_address(token_address)
        token_in = Web3.to_checksum_address(
            self.get_selected_chain().native_token_address)
        fee = int(pool["feeTier"])
        amount_in = int(native_token_trade_amount)

        # Call the get_price_input function to get the token amount for a given WETH amount
        try:
            print(
                f'get_token_native_output_price - getting price from Uniswap: token_in { token_in}, token_out: {token_out}, amount_in: {amount_in}, fee {fee}')
            token_amount = self.uniswap_client.get_price_output(
                token_in, token_out, amount_in, fee)
            print(f"Token amount for given WETH amount: {token_amount}")
            return token_amount
        except Exception as e:
            print(f"Error during price estimation: {e}")
            return -1

    def get_native_token_output_price(self, token_address, token_trade_amount, pool):
        token_in = Web3.to_checksum_address(token_address)
        token_out = Web3.to_checksum_address(
            self.get_selected_chain().native_token_address)
        fee = int(pool["feeTier"])

        # Call the get_price_output function to get the native token (WETH) amount for a given token amount
        try:
            print(
                f'getting price from Uniswap: token_in { token_in}, token_out: {token_out}, amount_in: {token_trade_amount}, fee {fee}')
            native_token_amount = self.uniswap_client.get_price_output(
                token_in, token_out, token_trade_amount, fee)
            print(
                f"Native token (WETH) amount for given token amount: {native_token_amount}")
            return native_token_amount
        except Exception as e:
            print(f"Error during price estimation: {e}")
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
            print("Warning: pair_balance is zero. Skipping this token.")
            return 1  # Replace this with a suitable default value
        else:
            holders = total_supply // pair_balance

        return holders

    def get_pools_with_native_token(self, past_time, min_liquidity_native_token, min_volume_usd):
        query_template = """
            {{
                pools(first: 1, orderBy: createdAtTimestamp, orderDirection: desc, where:{{{token_field}: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", createdAtTimestamp_gte: "{past_time}", totalValueLockedETH_gt: "{min_liquidity_native_token}", liquidity_gt: 0, volumeUSD_gt: {min_volume_usd}}}) {{
                    id
                    token0 {{
                        id
                        symbol
                        name
                    }}
                    token1 {{
                        id
                        symbol
                        name
                    }}
                    feeTier
                    liquidity
                    sqrtPrice
                    tick
                }}
            }}
        """
        queries = [
            query_template.format(token_field="token0", past_time=past_time,
                                  min_liquidity_native_token=min_liquidity_native_token, min_volume_usd=min_volume_usd),
            query_template.format(token_field="token1", past_time=past_time,
                                  min_liquidity_native_token=min_liquidity_native_token, min_volume_usd=min_volume_usd)
        ]

        all_pools = []
        # "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        url = self.get_selected_chain().uniswap_graph_url
        for query in queries:
            response = requests.post(url, json={"query": query})
            data = response.json()
            print(query)
            all_pools.extend(data["data"]["pools"])
        return all_pools

    def get_pool_address(self, factory_contract, token0_address, token1_address, pool):
        try:
            try:
                # Call the contract function that causes the error
                pool_fee = int(pool["feeTier"])
                return factory_contract.functions.getPool(Web3.to_checksum_address(token0_address), Web3.to_checksum_address(token1_address), pool_fee).call()
            except ContractLogicError:
                print(f"Execution reverted for token: {token1_address}")
                # You can decide to skip the token, retry after some delay, or take any other appropriate action
        except Exception as e:
            print(
                f"Error occurred while getting pair address for token {token1_address}: {e}")
            raise

    def get_new_tokens(self, factory_contract, past_time_hours=3, min_liquidity_native_token=1, min_volume_usd=5000):
        past_time = int((datetime.datetime.now() -
                        datetime.timedelta(hours=past_time_hours)).timestamp())
        pools_with_native_token = self.get_pools_with_native_token(
            past_time, min_liquidity_native_token, min_volume_usd)

        new_token_addresses = []
        for pool in pools_with_native_token:
            pool_address = self.get_pool_address(
                factory_contract, pool["token0"]["id"], pool["token1"]["id"], pool)
            token = pool["token0"]["id"]

            print(
                f'native token address: {self.get_selected_chain().native_token_address.lower()} token address: {token.lower()}')

            if token.lower() == self.get_selected_chain().native_token_address.lower():
                token = pool["token1"]["id"]
            if token != self.get_selected_chain().native_token_address and pool_address != '0x0000000000000000000000000000000000000000':
                new_token_addresses.append({
                    "token": token,
                    "pool_address": pool_address,
                    "pool": pool
                })
        return list(new_token_addresses)
