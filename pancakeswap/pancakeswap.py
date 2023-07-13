import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from eth_typing.evm import Address, ChecksumAddress
from web3 import Web3
from web3.exceptions import NameNotFound

AddressLike = Union[Address, ChecksumAddress]
MAX_UINT256 = 2**256 - 1


class Pancakeswap:
    """
    Wrapper around Pancakeswap contracts.
    """

    address: AddressLike
    version: int

    w3: Web3

    def _str_to_addr(self, s: Union[AddressLike, str]) -> Address:
        """Idempotent"""
        if isinstance(s, str):
            if s.startswith("0x"):
                return Address(bytes.fromhex(s[2:]))
            else:
                raise NameNotFound(f"Couldn't convert string '{s}' to AddressLike")
        else:
            return s

    # ------ Tx Utils ------------------------------------------------------------------
    def _deadline(self) -> int:
        """Get a predefined deadline. 10min by default (same as the Uniswap SDK)."""
        return int(time.time()) + 10 * 60

    def __init__(
        self,
        w3: Web3 = None,
        wallet_private_key=None,
        default_slippage: float = 0.01,
        use_testnet=False,
        factory_contract_addr: Optional[str] = None,
        router_contract_addr: Optional[str] = None,
    ) -> None:
        self.w3 = w3
        self.w3.eth.default_account = w3.eth.account.from_key(
            wallet_private_key
        ).address
        self.wallet_private_key = wallet_private_key
        self.default_slippage = default_slippage
        self.router_abi = self.load_abi("router")
        self.quoter_abi = self.load_abi("quoter")
        self.factory_abi = self.load_abi("factory")
        self.erc20_abi = self.load_abi("erc20")
        self.main_account = self.w3.eth.account.from_key(self.wallet_private_key)
        self.wallet_address = self.main_account.address
        # Get the quoter contract address
        quoter_mainnet_address = "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"
        quoter_testnet_address = "0xbC203d7f83677c7ed3F7acEc959963E7F4ECC5C2"

        router_mainnet_address = "0x1b81D678ffb9C0263b24A97847620C99d213eB14"
        router_testnet_address = "0x1b81D678ffb9C0263b24A97847620C99d213eB14"

        if use_testnet:
            quoter_contract_address = self._str_to_addr(quoter_testnet_address)
            router_contract_address = self._str_to_addr(router_testnet_address)
        else:
            quoter_contract_address = self._str_to_addr(quoter_mainnet_address)
            router_contract_address = self._str_to_addr(router_mainnet_address)
        self.w3 = w3
        # Create the quoter contract object
        self.quoter_contract = w3.eth.contract(
            address=w3.to_checksum_address(quoter_contract_address),
            abi=self.quoter_abi,
        )
        self.router_contract = w3.eth.contract(
            address=w3.to_checksum_address(router_contract_address),
            abi=self.router_abi,
        )
        self.spender_address = w3.to_checksum_address(
            "0x1b81D678ffb9C0263b24A97847620C99d213eB14"
        )

    def load_abi(self, name):
        path = os.path.join(os.path.dirname(__file__), "abis", f"{name}.abi")
        with open(path, "r") as f:
            return json.load(f)  # This parses the JSON into a Python object

    def check_approval(self, token_address: AddressLike) -> bool:
        token = self.w3.eth.contract(
            address=self._str_to_addr(token_address), abi=self.erc20_abi
        )
        params = {}
        allowance = token.functions.allowance(
            self.w3.eth.default_account, self._str_to_addr(self.spender_address)
        ).call()
        return allowance > 0

    def approve_tokens(self, token_address: AddressLike) -> Dict[str, Any]:
        token = self.w3.eth.contract(
            address=self._str_to_addr(token_address), abi=self.erc20_abi
        )
        transaction = token.functions.approve(
            self._str_to_addr(self.spender_address),  # Set the spender address
            MAX_UINT256,  # Approve max amount
        )
        estimate_gas = transaction.estimate_gas()

        gas_price = self.w3.eth.gas_price
        gas_limit = estimate_gas + int(estimate_gas * 0.1)  # Add 10% buffer

        # Build the transaction
        approve_transaction = transaction.build_transaction(
            {
                "gasPrice": gas_price,
                "gas": gas_limit,
                "from": self.w3.eth.default_account,
                "nonce": self.w3.eth.get_transaction_count(self.w3.eth.default_account),
            }
        )

        # Sign and send the transaction
        signed_transaction = self.w3.eth.account.sign_transaction(
            approve_transaction, self.wallet_private_key
        )
        tx_hash = self.w3.eth.send_raw_transaction(signed_transaction.rawTransaction)

        # Wait for the transaction to be mined
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "transaction_hash": tx_hash.hex(),
            "gas_used": receipt["gasUsed"],
        }

    def get_price_input(
        self,
        token0: AddressLike,  # input token
        token1: AddressLike,  # output token
        qty: int,
        fee: Optional[int] = None,
    ) -> int:
        params = {
            "tokenIn": self.w3.to_checksum_address(token0),
            "tokenOut": self.w3.to_checksum_address(token1),
            "amount": int(qty),
            "fee": int(fee),
            "sqrtPriceLimitX96": 0,
        }

        response = self.quoter_contract.functions.quoteExactOutputSingle(params).call()
        amount = response[0]

        return amount

    def get_price_output(
        self,
        token0: AddressLike,
        token1: AddressLike,
        qty: int,
        fee: Optional[int] = None,
    ) -> int:
        params = {
            "tokenIn": self.w3.to_checksum_address(token0),
            "tokenOut": self.w3.to_checksum_address(token1),
            "amountIn": int(qty),
            "fee": int(fee),
            "sqrtPriceLimitX96": 0,
        }

        response = self.quoter_contract.functions.quoteExactInputSingle(params).call()
        amount = response[0]

        return amount

    def make_trade(
        self,
        token_in: AddressLike,
        token_out: AddressLike,
        amount: int,
        fee: Optional[int] = None,
        slippage: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.check_approval(token_in):
            self.approve_tokens(token_in)

        if not self.check_approval(token_out):
            self.approve_tokens(token_out)
        if slippage is None:
            slippage = self.default_slippage

        min_tokens_bought = int(
            (1 - slippage) * self.get_price_output(token_in, token_out, amount, fee)
        )

        sqrt_price_limit_x96 = 0
        # Prepare the function parameters
        params = {
            "tokenIn": Web3.to_checksum_address(token_in),
            "tokenOut": Web3.to_checksum_address(token_out),
            "fee": fee,
            "recipient": self.wallet_address,
            "deadline": self._deadline(),
            "amountIn": amount,
            "amountOutMinimum": min_tokens_bought,  # here you might want to specify minimum amount of tokenOut you want to receive
            "sqrtPriceLimitX96": sqrt_price_limit_x96,
        }

        # Prepare the transaction
        transaction = self.router_contract.functions.exactInputSingle(params)
        # Build the transaction
        transaction_dict = {
            "value": 0,
            "gasPrice": self.w3.eth.gas_price,
            "from": self.wallet_address,
            "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
        }

        # Build the transaction
        trade_transaction = transaction.build_transaction(transaction_dict)

        # Sign and send the transaction
        signed_transaction = self.main_account.sign_transaction(trade_transaction)
        tx_hash = self.w3.eth.send_raw_transaction(signed_transaction.rawTransaction)

        # Wait for the transaction to be mined
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "transaction_hash": tx_hash.hex(),
            "gas_used": receipt["gasUsed"],
        }
