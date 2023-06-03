import datetime
import json
import logging
from ast import List
from typing import List, Optional, Union

from eth_typing import Address, ChecksumAddress
from uniswap import Uniswap

from defi.price_provider import PriceProvider
from managers.blockchain_manager import BlockchainManager
from managers.subgraph_manager import SubgraphManager
from models.graph_structures import Pool
from simulation.simulated_price_provider import SimulatedPriceProvider


class ProtocolManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # Delay between retry attempts in seconds

    def __init__(self, blockchain_manager: BlockchainManager, demo_mode: True):
        self.stablecoin_tokens = self.load_stablecoin_data()
        self.subgraph_manager = SubgraphManager(blockchain_manager)
        self.blockchain_manager: BlockchainManager = blockchain_manager

        if demo_mode:
            self.dex_price_provider = SimulatedPriceProvider(
                Uniswap(
                    address=self.blockchain_manager.get_wallet_address(),
                    private_key=self.blockchain_manager.get_wallet_private_key(),
                    version=3,
                ),
                self.blockchain_manager,
            )
        else:
            self.dex_price_provider = PriceProvider(
                Uniswap(
                    address=self.blockchain_manager.get_wallet_address(),
                    private_key=self.blockchain_manager.get_wallet_private_key(),
                    version=3,
                )
            )

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

    def is_stablecoin(self, token_address):
        current_chain = self.blockchain_manager.get_current_chain().name
        stablecoin_tokens = self.stablecoin_tokens.setdefault(current_chain, {})

        for stablecoin_address, token_data in stablecoin_tokens.items():
            if token_address.lower() == stablecoin_address:
                return True
        return False

    async def get_tokens(
        self,
        factory_contract,
        past_time_hours=3,
        min_liquidity_usd=1,
        min_volume_usd=5000,
    ):
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
                past_time, min_liquidity_usd, min_volume_usd
            )

            new_token_addresses = []
            for pool in pools_with_native_token:
                # token0 = pool["inputTokens"][0].get("id")
                # token1 = pool["inputTokens"][1].get("id")
                # pool_address = self.get_pool_address(
                #     factory_contract, pool.token0, pool.token1, pool.fee
                # )
                pool_address = pool.id
                token_address = pool.token0.id
                fee = pool.fee.basis_points

                if token_address.lower() == native_token_address.lower():
                    token_address = pool.token1.id
                if (
                    token_address != native_token_address
                    and token_address != self.is_stablecoin(token_address)
                    and pool_address != "0x0000000000000000000000000000000000000000"
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
            logging.error(f"Error occurred in get_tokens: {str(error_message)}")
            return []  # Return empty list on error, adjust as needed

    # Given token_trade_amount for native_token_address,
    # returns the maximum output amount of token token_address

    def get_max_native_for_token(self, token_address, token_trade_amount, fee):
        token_in = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        token_out = self.blockchain_manager.web3_instance.to_checksum_address(
            self.blockchain_manager.get_current_chain().native_token_address
        )
        logging.info(
            f"getting price input from dex: token_in { token_in}, \
                token_out: {token_out}, \
                    amount_in: {token_trade_amount}, fee {fee}"
        )
        try:
            native_token_amount = self.dex_price_provider.get_price_input(
                token_in, token_out, token_trade_amount, fee
            )
            logging.info(
                f"Native token (WETH) amount for given token amount: {native_token_amount}"
            )
            return native_token_amount
        except ValueError as error_message:
            logging.error(
                f"Error during price estimation: {error_message}", exc_info=True
            )
            return -1

    # Returns the minimum amount of token token_address required to
    # buy token_trade_amount of native_token_address.

    def get_min_token_for_native(self, token_address, token_trade_amount, fee):
        token_in = self.blockchain_manager.web3_instance.to_checksum_address(
            token_address
        )
        token_out = self.blockchain_manager.web3_instance.to_checksum_address(
            self.blockchain_manager.get_current_chain().native_token_address
        )
        logging.info(
            f"getting price output from dex: token_in: {token_in}, token_out: {token_out}, amount_in: {token_trade_amount}, fee: {fee}"
        )

        try:
            self.validate_get_price_inputs(token_in, token_out, token_trade_amount, fee)
            # logging.info("Uniswap price inputs valid!")
        except ValueError as error:
            logging.info(f"Error in Uniswap price inputs: {error}")

        try:
            # dex_price_provider
            native_token_amount = self.dex_price_provider.get_price_output(
                token_in, token_out, token_trade_amount, fee
            )
            return native_token_amount
        except Exception as error:
            logging.error(f"Error during price estimation: {error}", exc_info=True)
            # Handle the error or invalid price estimation
            logging.info("Invalid token price estimation. Cannot proceed further.")
            return -1
