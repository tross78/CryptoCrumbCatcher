import asyncio
import os

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware

from pancakeswap import Pancakeswap

# Load the .env file
load_dotenv(".env")


def get_token_balance(w3, token_address, wallet_address):
    # The ERC-20 ABI includes the `balanceOf` function, which is what we want to call
    erc20_abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    # Create a contract instance
    token_contract = w3.eth.contract(address=token_address, abi=erc20_abi)

    # Call the `balanceOf` function from the contract and get the result
    balance = token_contract.functions.balanceOf(wallet_address).call()

    return balance


async def main(use_testnet):
    if use_testnet:
        provider_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
        token_in = "0xae13d989daC2f0dEbFf460aC112a837C89BAa7cd"  # WBNB
        token_out = "0xFa60D973F7642B748046464e165A65B7323b0DEE"

    else:
        provider_url = "https://serene-few-daylight.bsc.discover.quiknode.pro/8e6bd72b59001bb462213064d69c6a6bc8f428e4/"
        token_in = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"  # WBNB
        token_out = "0x55d398326f99059ff775485246999027b3197955"

    os.environ["PROVIDER"] = provider_url
    wallet_private_key = os.environ["WALLET_PRIVATE_KEY"]
    w3 = Web3(Web3.HTTPProvider(provider_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    w3.eth.default_account = w3.eth.account.from_key(wallet_private_key).address
    client = Pancakeswap(w3, wallet_private_key, use_testnet=use_testnet)

    # print(
    #     client.get_price_output(
    #         token_in,
    #         token_out,
    #         10000000000000,
    #         10000,
    #     )
    # )
    # print(
    #     client.get_price_input(
    #         token_in,
    #         token_out,
    #         2350819554397474,
    #         100,
    #     )
    #
    balance = get_token_balance(w3, token_out, w3.eth.default_account)
    print(
        client.make_trade(
            token_out,
            token_in,
            balance,
            10000,
        )
    )


asyncio.run(main(use_testnet=True))
