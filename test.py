# Online Python compiler (interpreter) to run Python online.
# Write Python 3 code in this online editor and run it.
import asyncio
import os
from typing import Union

from eth_typing.evm import Address, ChecksumAddress
from web3.exceptions import NameNotFound

AddressLike = Union[Address, ChecksumAddress]
from web3 import Web3


def _str_to_addr(s: Union[AddressLike, str]) -> Address:
    """Idempotent"""
    if isinstance(s, str):
        if s.startswith("0x"):
            return Address(bytes.fromhex(s[2:]))
        else:
            raise NameNotFound(f"Couldn't convert string '{s}' to AddressLike")
    else:
        return s


def get_token_price(
    w3,
    input_token_address,
    output_token_address,
    input_token_amount,
    output_token_decimals,
    pool_fee,
):
    # Get the quoter contract address
    quoter_contract_address = _str_to_addr("0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997")

    # Get the quoter contract ABI
    quoterV2_abi = [
        {
            "inputs": [
                {"internalType": "address", "name": "_deployer", "type": "address"},
                {"internalType": "address", "name": "_factory", "type": "address"},
                {"internalType": "address", "name": "_WETH9", "type": "address"},
            ],
            "stateMutability": "nonpayable",
            "type": "constructor",
        },
        {
            "inputs": [],
            "name": "WETH9",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "deployer",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "factory",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "int256", "name": "amount0Delta", "type": "int256"},
                {"internalType": "int256", "name": "amount1Delta", "type": "int256"},
                {"internalType": "bytes", "name": "path", "type": "bytes"},
            ],
            "name": "pancakeV3SwapCallback",
            "outputs": [],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "bytes", "name": "path", "type": "bytes"},
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            ],
            "name": "quoteExactInput",
            "outputs": [
                {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
                {
                    "internalType": "uint160[]",
                    "name": "sqrtPriceX96AfterList",
                    "type": "uint160[]",
                },
                {
                    "internalType": "uint32[]",
                    "name": "initializedTicksCrossedList",
                    "type": "uint32[]",
                },
                {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
            ],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "tokenIn",
                            "type": "address",
                        },
                        {
                            "internalType": "address",
                            "name": "tokenOut",
                            "type": "address",
                        },
                        {
                            "internalType": "uint256",
                            "name": "amountIn",
                            "type": "uint256",
                        },
                        {"internalType": "uint24", "name": "fee", "type": "uint24"},
                        {
                            "internalType": "uint160",
                            "name": "sqrtPriceLimitX96",
                            "type": "uint160",
                        },
                    ],
                    "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                    "name": "params",
                    "type": "tuple",
                }
            ],
            "name": "quoteExactInputSingle",
            "outputs": [
                {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
                {
                    "internalType": "uint160",
                    "name": "sqrtPriceX96After",
                    "type": "uint160",
                },
                {
                    "internalType": "uint32",
                    "name": "initializedTicksCrossed",
                    "type": "uint32",
                },
                {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
            ],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "bytes", "name": "path", "type": "bytes"},
                {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            ],
            "name": "quoteExactOutput",
            "outputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {
                    "internalType": "uint160[]",
                    "name": "sqrtPriceX96AfterList",
                    "type": "uint160[]",
                },
                {
                    "internalType": "uint32[]",
                    "name": "initializedTicksCrossedList",
                    "type": "uint32[]",
                },
                {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
            ],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "tokenIn",
                            "type": "address",
                        },
                        {
                            "internalType": "address",
                            "name": "tokenOut",
                            "type": "address",
                        },
                        {
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256",
                        },
                        {"internalType": "uint24", "name": "fee", "type": "uint24"},
                        {
                            "internalType": "uint160",
                            "name": "sqrtPriceLimitX96",
                            "type": "uint160",
                        },
                    ],
                    "internalType": "struct IQuoterV2.QuoteExactOutputSingleParams",
                    "name": "params",
                    "type": "tuple",
                }
            ],
            "name": "quoteExactOutputSingle",
            "outputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {
                    "internalType": "uint160",
                    "name": "sqrtPriceX96After",
                    "type": "uint160",
                },
                {
                    "internalType": "uint32",
                    "name": "initializedTicksCrossed",
                    "type": "uint32",
                },
                {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
            ],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    # Create the quoter contract object
    quoter_contract = w3.eth.contract(
        address=w3.to_checksum_address(quoter_contract_address), abi=quoterV2_abi
    )

    params = {
        "tokenIn": w3.to_checksum_address(input_token_address),
        "tokenOut": w3.to_checksum_address(output_token_address),
        "amount": int(input_token_amount),
        "fee": int(pool_fee),
        "sqrtPriceLimitX96": 0,
    }

    # Call the quoteExactOutputSingle method
    amount_in = quoter_contract.functions.quoteExactOutputSingle(params).call()

    # Return the amount in
    return amount_in


async def main():
    provider_url = (
        "https://eth-mainnet.g.alchemy.com/v2/K9oT4wm74HHPBwJVYPuEPihhkhhChUOO"
    )
    os.environ["PROVIDER"] = provider_url
    w3 = Web3(Web3.HTTPProvider(provider_url))
    # print(
    #     get_token_price(
    #         w3,
    #         "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
    #         "0x55d398326f99059ff775485246999027b3197955",
    #         1000000000000000,
    #         18,
    #         100,
    #     )
    # )
    print(
        get_token_price(
            w3,
            "0x6982508145454ce325ddbe47a25d4ec3d2311933",
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            1000000000000000,
            18,
            100,
        )
    )


asyncio.run(main())
