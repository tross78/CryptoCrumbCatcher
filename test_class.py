import logging
from decimal import Decimal

from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from utils import calculate_estimated_net_token_amount_wei_after_fees


class TestClass:
    def __init__(
        self, data_manager: DataManagement, blockchain_manager: BlockchainManager
    ):
        self.blockchain_manager = blockchain_manager
        self.data_manager = data_manager
        self.profit_margin = Decimal("0.01")

    def calculate_gas_cost(self, num_transactions=2):
        gas_limit_per_transaction = self.blockchain_manager.gas_limit_per_transaction
        gas_price_gwei = self.blockchain_manager.web3_instance.eth.gas_price
        gas_cost_per_transaction_weth = self.blockchain_manager.web3_instance.from_wei(
            gas_price_gwei * gas_limit_per_transaction, "ether"
        )
        total_gas_fees = gas_cost_per_transaction_weth * num_transactions
        return total_gas_fees

    # def calculate_break_even(self, initial_token_amount, fee, num_transactions=2):
    #     total_gas_fees = self.calculate_gas_cost(num_transactions)
    #     net_token_amount = calculate_estimated_net_token_amount_wei_after_fees(
    #         fee, initial_token_amount
    #     )
    #     print(f"gas fees: {total_gas_fees}")
    #     print(f"net token amount after fees: {net_token_amount}")
    #     print(f"total costs: {(initial_token_amount - net_token_amount)}")
    #     break_even = (
    #         Decimal(initial_token_amount)
    #         + total_gas_fees
    #         + (initial_token_amount - net_token_amount)
    #     )
    #     return break_even

    def calculate_net_amount_and_costs(
        self, initial_token_amount, fee, num_transactions=2
    ):
        total_gas_fees = self.calculate_gas_cost(num_transactions)
        net_token_amount = calculate_estimated_net_token_amount_wei_after_fees(
            fee, initial_token_amount
        )
        costs = total_gas_fees + (initial_token_amount - net_token_amount)
        net_amount = initial_token_amount - costs
        return net_amount, costs

    def calculate_roi_multiplier(self, fee):
        # initial_investment = Decimal(self.data_manager.config["trade_amount_eth"])
        # net_amount, costs = self.calculate_net_amount_and_costs(initial_investment, fee)

        # break_even = initial_investment + costs

        # desired_profit_percentage = self.profit_margin
        # desired_profit_value = break_even * desired_profit_percentage

        # expected_roi_value = break_even + desired_profit_value
        # expected_roi_multiplier = expected_roi_value / initial_investment

        # logging.info(
        #     f"Initial investment: {initial_investment} \
        #         Net amount: {net_amount} \
        #         Costs: {costs} \
        #         Profit percentage: {desired_profit_percentage} \
        #         Multiplier: {expected_roi_multiplier}"
        # )

        # return expected_roi_multiplier
        return self.calculate_gas_cost(2)
