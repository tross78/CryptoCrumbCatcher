from web3 import Web3
def get_percentage_from_string(s):
    if isinstance(s, str):
            # Split the string using the '/' character
            num, denom = s.split('/')

            # Convert the substrings to numbers (floats)
            num = float(num)
            denom = float(denom)

            # Calculate the percentage
            percentage = (num / denom) * 100

            return percentage
    else:
        return 0

def get_block_number_by_timestamp(w3, target_timestamp, lower_bound=0, upper_bound=None):
    if upper_bound is None:
        upper_bound = w3.eth.blockNumber

    while lower_bound < upper_bound:
        middle = (lower_bound + upper_bound) // 2
        middle_block = w3.eth.getBlock(middle)
        middle_timestamp = middle_block["timestamp"]

        if middle_timestamp < target_timestamp:
            lower_bound = middle + 1
        elif middle_timestamp > target_timestamp:
            upper_bound = middle - 1
        else:
            return middle

    return lower_bound

def encode_position_key(token0, token1, fee, tick_lower, tick_upper):
    # Token 0 and token 1 should be input as their token ID in hex format.
    # Fee should be input as an integer.
    # Tick lower and tick upper should be input as an integer.
    return Web3.solidityKeccak(
        ['address', 'address', 'uint24', 'int24', 'int24'],
        [token0, token1, fee, tick_lower, tick_upper]
    )
