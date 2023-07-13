import datetime
import json
from ast import List
from typing import List, Optional, Union

from eth_typing import Address, ChecksumAddress
from uniswap import Uniswap
from web3.middleware import geth_poa_middleware

from defi.dex_client_wrapper import DexClientWrapper
from logger_config import logger
from managers.blockchain_manager import BlockchainManager
from managers.subgraph_manager import SubgraphManager
from managers.token_blacklist_manager import TokenBlacklistManager
from models.graph_structures import Pool
from pancakeswap import Pancakeswap
from simulation.simulated_dex_client_wrapper import SimulatedDexClientWrapper


class ProtocolManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # Delay between retry attempts in seconds

    def __init__(
        self,
        blockchain_manager: BlockchainManager,
        demo_mode: True,
        simulate_pump_mode: False,
    ):
        self.stablecoin_tokens = self.load_stablecoin_data()
        self.subgraph_manager = SubgraphManager(blockchain_manager)
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.token_blacklist_manager: TokenBlacklistManager = TokenBlacklistManager(
            blockchain_manager
        )
        self.demo_mode = demo_mode
        self.simulate_pump_mode = simulate_pump_mode

        dex_name = self.blockchain_manager.get_supported_dex()

        dex_client = Uniswap(
            address=self.blockchain_manager.get_wallet_address(),
            private_key=self.blockchain_manager.get_wallet_private_key(),
            version=3,
        )
        if simulate_pump_mode:
            self.dex_client_wrapper = SimulatedDexClientWrapper(
                dex_client,
                self.blockchain_manager,
            )
        else:
            if dex_name == "pancakeswap":
                dex_client = Pancakeswap(
                    w3=self.blockchain_manager.web3_instance,
                    wallet_private_key=self.blockchain_manager.wallet_private_key,
                )

            self.dex_client_wrapper = DexClientWrapper(dex_client)
        dex_client.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    def validate_get_price_inputs(
        self,
        token0: Union[Address, ChecksumAddress],
        token1: Union[Address, ChecksumAddress],
        qty: int,
        fee: Optional[int] = None,
        route: Optional[List[Union[Address, ChecksumAddress]]] = None,
    ) -> bool:
        # Validate token addresses
        if isinstance(token0, str):
            token0 = ChecksumAddress(token0)
        elif not isinstance(token0, (Address, ChecksumAddress)):
            raise ValueError("Invalid token0 address")

        if isinstance(token1, str):
            token1 = ChecksumAddress(token1)
        elif not isinstance(token1, (Address, ChecksumAddress)):
            raise ValueError("Invalid token1 address")

        # Validate qty
        if not isinstance(qty, int) or qty <= 0:
            raise ValueError("Invalid quantity")

        # Validate fee
        if fee is not None and (not isinstance(fee, int) or fee < 0):
            raise ValueError("Invalid fee")

        # Validate route
        if route is not None:
            if not isinstance(route, list):
                raise ValueError("Invalid route format")
            for i, address in enumerate(route):
                if isinstance(address, str):
                    route[i] = ChecksumAddress(address)
                elif not isinstance(address, (Address, ChecksumAddress)):
                    raise ValueError(f"Invalid route address at index {i}")

        # All inputs are valid
        return True

    def load_stablecoin_data(self):
        with open("data/stablecoins.json", "r") as json_file:
            return json.load(json_file)

    def is_stablecoin(self, token_address: str) -> bool:
        current_chain = self.blockchain_manager.get_current_chain().name
        self.stablecoin_tokens.setdefault(current_chain, {})
        return token_address.lower() in (
            address.lower() for address in self.stablecoin_tokens[current_chain].keys()
        )

    async def get_tokens(
        self,
        past_time_hours=3,
        min_liquidity_usd=1,
        max_liquidity_usd=100000,
        min_volume_usd=5000,
    ):
        logger.info("Trying to get new tokens here:")
        native_token_address = (
            self.blockchain_manager.get_current_chain().native_token_address
        )
        try:
            past_time = int(
                (
                    datetime.datetime.now() - datetime.timedelta(hours=past_time_hours)
                ).timestamp()
            )
            pools_with_native_token: List[
                Pool
            ] = self.subgraph_manager.get_pools_with_native_token(
                past_time, min_liquidity_usd, max_liquidity_usd, min_volume_usd
            )

            new_token_addresses = []
            for pool in pools_with_native_token:
                pool_address = pool.id
                token_address = pool.token0.id
                fee = pool.fee.basis_points

                if token_address.lower() == native_token_address.lower():
                    token_address = pool.token1.id
                if (
                    (token_address != native_token_address)
                    and (not self.is_stablecoin(token_address))
                    and (pool_address != "0x0000000000000000000000000000000000000000")
                    and not (
                        await self.token_blacklist_manager.is_token_blacklisted(
                            token_address
                        )
                    )
                ):
                    new_token_addresses.append(
                        {
                            "token": token_address,
                            "pool_address": pool_address,
                            "fee": fee,
                        }
                    )
            return list(new_token_addresses)
        except Exception as error_message:
            logger.error(f"Error occurred in get_tokens: {str(error_message)}")
            return []  # Return empty list on error, adjust as needed

    # Given token_trade_amount for native_token_address,
    # returns the maximum output amount of token token_address

    async def get_max_native_for_token(self, token_address, token_trade_amount, fee):
        token_in = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        token_out = self.blockchain_manager.web3_instance.to_checksum_address(
            self.blockchain_manager.get_current_chain().native_token_address
        )
        logger.info(
            f"getting price input from dex: token_in { token_in}, \
                token_out: {token_out}, \
                    amount_in: {token_trade_amount}, fee {fee}"
        )
        try:
            native_token_amount = await self.dex_client_wrapper.get_price_input(
                token_in, token_out, token_trade_amount, fee
            )
            logger.info(
                f"Native token (WETH) amount for given token amount: {native_token_amount}"
            )
            return native_token_amount
        except Exception as error:
            # logger.error(
            #     f"Error during price estimation: {error_message}", exc_info=False
            # )
            return -1

    # Returns the minimum amount of token token_address required to
    # buy token_trade_amount of native_token_address.

    async def get_min_token_for_native(self, token_address, token_trade_amount, fee):
        token_in = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        token_out = self.blockchain_manager.web3_instance.to_checksum_address(
            self.blockchain_manager.get_current_chain().native_token_address
        )
        logger.info(
            f"getting price output from dex: token_in: {token_in}, token_out: {token_out}, amount_in: {token_trade_amount}, fee: {fee}"
        )

        try:
            self.validate_get_price_inputs(token_in, token_out, token_trade_amount, fee)
            # logger.info("Uniswap price inputs valid!")
        except ValueError as error:
            logger.info(f"Error in Uniswap price inputs: {error}")

        try:
            # dex_client_wrapper
            native_token_amount = await self.dex_client_wrapper.get_price_output(
                token_in, token_out, token_trade_amount, fee
            )
            return native_token_amount
        except Exception as error:
            # logger.error(f"Error during price estimation: {error}", exc_info=False)
            # # Handle the error or invalid price estimation
            # logger.info("Invalid token price estimation. Cannot proceed further.")
            return -1

    def get_pool_instance(self, token_0, token_1, fee):
        token_0 = self.blockchain_manager.web3_instance.to_checksum_address(token_0)
        token_1 = self.blockchain_manager.web3_instance.to_checksum_address(token_1)
        try:
            return self.dex_client_wrapper.get_pool_instance(token_0, token_1, fee)
        except Exception as error:
            return None

    def make_trade(self, token_address, native_token_address, trade_amount, fee):
        token_address = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        native_token_address = (
            self.blockchain_manager.web3_instance.to_checksum_address(
                native_token_address
            )
        )
        self.dex_client_wrapper.make_trade(
            token_address, native_token_address, trade_amount, fee
        )

    def make_trade_output(self, token_address, native_token_address, trade_amount):
        token_address = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        self.dex_client_wrapper.make_trade_output(
            token_address, native_token_address, trade_amount
        )

    def approve(self, token_address, max_approval):
        token_address = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        if not self.demo_mode:
            self.dex_client_wrapper.approve(token_address, max_approval)
