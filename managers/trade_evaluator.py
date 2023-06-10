import logging
from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
from models.trade_data import PotentialTrade, TradeData
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

    def calculate_gas_fee_in_eth(self):
        average_gas_price = self.blockchain_manager.web3_instance.eth.gas_price
        estimated_gas_limit = 150000
        gas_fee = average_gas_price * estimated_gas_limit
        return gas_fee

    def calculate_net_amount_and_costs(self, token_base_value, fee, num_transactions=2):
        total_gas_cost = self.blockchain_manager.calculate_gas_cost_wei(
            num_transactions
        )
        net_token_amount = calculate_estimated_net_token_amount_wei_after_fees(
            fee, token_base_value, num_transactions
        )
        net_amount = net_token_amount - total_gas_cost
        fees = token_base_value - net_amount
        costs = total_gas_cost + fees
        return net_amount, costs

    def calculate_roi_multiplier(
        self, potential_trade: PotentialTrade, trade_data: TradeData
    ):
        if (
            potential_trade.token_address
            == "0xeca66820ed807c096e1bd7a1a091cd3d3152cc79"
        ):
            abc = "abc"
        orig_investment = Decimal(trade_data.original_investment_eth)
        # selling to ETH will cost some ETH (fees, slippage)
        net_amount, costs = self.calculate_net_amount_and_costs(
            orig_investment, potential_trade.fee, 2
        )
        desired_profit_percentage = 1 + self.profit_margin
        expected_roi_value = (orig_investment + costs) * desired_profit_percentage
        expected_roi_multiplier = expected_roi_value / orig_investment

        logging.info(
            f"Initial investment: {orig_investment} \
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
            token_balance = self.wallet_manager.get_token_balance(token_address)
            if token_balance < trade_amount:
                logging.info(
                    f"Not enough {token_address} tokens balance to make the trade. Have {token_balance} need {trade_amount}"
                )
                return False

        return True
