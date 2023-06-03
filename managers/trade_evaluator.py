import logging
from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
from utils import calculate_estimated_net_token_amount_wei_after_fees


class TradeEvaluator:
    def __init__(
        self,
        blockchain_manager: BlockchainManager,
        data_manager: DataManagement,
        wallet_manager: WalletManager,
        protocol_manager: ProtocolManager,
        profit_margin: Decimal,
    ):
        self.blockchain_manager = blockchain_manager
        self.data_manager = data_manager
        self.wallet_manager = wallet_manager
        self.protocol_manager = protocol_manager
        self.profit_margin = profit_margin

    # def break_even_roi(self, initial_token_amount, fee, num_transactions=2):
    #     gas_limit_per_transaction = (
    #         self.blockchain_manager.gas_limit_per_transaction
    #     )  # Example gas limit per transaction 150000
    #     # Get the current gas price in Gwei
    #     gas_price_gwei = self.blockchain_manager.web3_instance.eth.gas_price
    #     gas_cost_per_transaction_weth = self.blockchain_manager.web3_instance.from_wei(
    #         gas_price_gwei * gas_limit_per_transaction, "ether"
    #     )
    #     total_gas_fees = gas_cost_per_transaction_weth * num_transactions
    #     net_token_amount = calculate_estimated_net_token_amount_wei_after_fees(
    #         fee, initial_token_amount
    #     )
    #     break_even = (
    #         Decimal(initial_token_amount)
    #         + total_gas_fees
    #         + (initial_token_amount - net_token_amount)
    #     )
    #     return break_even

    def calculate_gas_cost(self, num_transactions=2):
        gas_limit_per_transaction = self.blockchain_manager.gas_limit_per_transaction
        gas_price_gwei = self.blockchain_manager.web3_instance.eth.gas_price
        gas_cost_per_transaction_weth = self.blockchain_manager.web3_instance.from_wei(
            gas_price_gwei * gas_limit_per_transaction, "ether"
        )
        total_gas_fees = gas_cost_per_transaction_weth * num_transactions
        return total_gas_fees

    def calculate_break_even(self, initial_token_amount, fee, num_transactions=2):
        total_gas_fees = self.calculate_gas_cost(num_transactions)
        net_token_amount = calculate_estimated_net_token_amount_wei_after_fees(
            fee, initial_token_amount
        )
        break_even = (
            Decimal(initial_token_amount)
            + total_gas_fees
            + (initial_token_amount - net_token_amount)
        )
        return break_even

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
        initial_investment = Decimal(self.data_manager.config["trade_amount_eth"])
        net_amount, costs = self.calculate_net_amount_and_costs(initial_investment, fee)

        break_even = initial_investment + costs

        desired_profit_percentage = self.profit_margin
        desired_profit_value = break_even * desired_profit_percentage

        expected_roi_value = break_even + desired_profit_value
        expected_roi_multiplier = expected_roi_value / initial_investment

        logging.info(
            f"Initial investment: {initial_investment} \
                Net amount: {net_amount} \
                Costs: {costs} \
                Profit percentage: {desired_profit_percentage} \
                Multiplier: {expected_roi_multiplier}"
        )

        return expected_roi_multiplier

    def has_balance_for_trade(self, token_address, trade_amount, action):
        estimated_gas_limit = 150000
        num_trades = 2  # Number of trades to consider

        # Get the average gas price in Gwei
        average_gas_price = self.blockchain_manager.web3_instance.eth.gas_price
        gas_fee = average_gas_price * estimated_gas_limit * num_trades

        if action == TradeAction.BUY:
            native_token_balance = self.wallet_manager.get_native_token_balance()
            needed_token_balance = trade_amount + gas_fee
            if native_token_balance < needed_token_balance:
                logging.info(
                    f"Not enough Native Token balance {native_token_balance} to make the trade. Need {needed_token_balance}"
                )
                return False
        elif action == TradeAction.SELL:
            if token_address not in self.wallet_manager.get_tokens():
                logging.info(f"{token_address} is not in the token balance dictionary.")
                return False
            token_balance = self.wallet_manager.get_token_balance(token_address)
            if token_balance < trade_amount:
                logging.info(
                    f"Not enough {token_address} tokens balance to make the trade. Have {token_balance} need {trade_amount}"
                )
                return False

        return True
