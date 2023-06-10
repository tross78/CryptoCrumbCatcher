from decimal import Decimal


def has_value_increased(token_amount_start, token_amount_end):
    if token_amount_end == 0:
        raise ValueError(
            "End token amount is zero. This could indicate an extreme price increase or a problem with the token."
        )
    return token_amount_end < token_amount_start


def calculate_estimated_net_token_amount_wei_after_fees(
    fee, token_amount, num_transactions
):
    fee_percentage = fee / 1000000
    slippage_tolerance = Decimal("0.01")
    net_token_amount_wei = Decimal(token_amount) / (
        Decimal("1")
        + ((Decimal(fee_percentage) + slippage_tolerance) * num_transactions)
    )
    return net_token_amount_wei


def get_percentage_from_string(percentage_string):
    if isinstance(percentage_string, str):
        # Split the string using the '/' character
        num, denom = percentage_string.split("/")

        # Convert the substrings to numbers (floats)
        num = float(num)
        denom = float(denom)

        # Calculate the percentage
        percentage = (num / denom) * 100

        return percentage
    else:
        return 0


def get_block_number_by_timestamp(
    web3_instance, target_timestamp, lower_bound=0, upper_bound=None
):
    if upper_bound is None:
        upper_bound = web3_instance.eth.blockNumber

    while lower_bound < upper_bound:
        middle = (lower_bound + upper_bound) // 2
        middle_block = web3_instance.eth.getBlock(middle)
        middle_timestamp = middle_block["timestamp"]

        if middle_timestamp < target_timestamp:
            lower_bound = middle + 1
        elif middle_timestamp > target_timestamp:
            upper_bound = middle - 1
        else:
            return middle

    return lower_bound
