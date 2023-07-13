from uniswap import Uniswap
from web3 import Web3
from web3.middleware import geth_poa_middleware

from managers.blockchain_manager import BlockchainManager
from models.chain_constants import SelectedChain


def get_select_chain_input(selected_chain_options):
    while True:
        print("Available chain options:")
        for i, option in enumerate(selected_chain_options, start=1):
            print(f"{i}. {option.value}")

        user_input = input("Enter the number corresponding to your selected chain: ")

        try:
            option_index = int(user_input) - 1
            if 0 <= option_index < len(selected_chain_options):
                selected_chain = selected_chain_options[option_index]
                return selected_chain
        except ValueError:
            pass

        print("Invalid input. Please try again.")


user_selected_chain = get_select_chain_input(list(SelectedChain))
print(f"Selected chain: {user_selected_chain.value}")


blockchain_manager = BlockchainManager(user_selected_chain)

uniswap_client = Uniswap(
    address=blockchain_manager.get_wallet_address(),
    private_key=blockchain_manager.get_wallet_private_key(),
    version=3,
)
# uniswap_client.w3.middleware_onion.inject(
#     geth_poa_middleware, layer=0
# )  # Required for some Ethereum networks

# mainnet_token0 = Web3.to_checksum_address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
# mainnet_token1 = Web3.to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")

# print(
#     uniswap_client.get_price_output(
#         mainnet_token0, mainnet_token1, 1000000000000000000, 10000
#     )
# )

# goerli_token0 = Web3.to_checksum_address(
#     "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
# )  # UNI
# goerli_token1 = Web3.to_checksum_address(
#     "0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6"
# )  # WETH

#    "0x6982508145454ce325ddbe47a25d4ec3d2311933",
#         "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",

print(
    uniswap_client.get_price_output(
        Web3.to_checksum_address("0x6982508145454ce325ddbe47a25d4ec3d2311933"),
        Web3.to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
        100000000000000000,
        3000,
    )
)

# buys 0.1 worth of UNI with WETH
# uniswap_client.make_trade(goerli_token1, goerli_token0, 100000000000000000)

# sells all of UNI (2.295) for WETH
# uniswap_client.make_trade(goerli_token0, goerli_token1, int(2.295e18))
