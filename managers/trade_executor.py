import logging
from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
from models.trade_data import PotentialTrade, TradeData
from token_info.token_monitor import TokenMonitor
from utils import calculate_estimated_net_token_amount_wei_after_fees


class TradeExecutor:
    def __init__(
        self,
        blockchain_manager: BlockchainManager,
        token_monitor: TokenMonitor,
        wallet_manager: WalletManager,
        protocol_manager: ProtocolManager,
        demo_mode=True,
    ):
        self.blockchain_manager = blockchain_manager
        self.wallet_manager = wallet_manager
        self.protocol_manager = protocol_manager
        self.token_monitor = token_monitor
        self.demo_mode = demo_mode

    async def trade_token(
        self,
        potential_trade: PotentialTrade,
        trade_data: TradeData,
        action,
    ):
        try:
            gas_fee = self.blockchain_manager.calculate_gas_cost_wei(1)
            token_balance = self.wallet_manager.get_token_balance(
                potential_trade.token_address
            )  # balance for token in wallet

            if action == TradeAction.BUY:
                # amount of token for eth

                trade_data.expected_amount = (
                    await self.protocol_manager.get_min_token_for_native(
                        potential_trade.token_address,
                        trade_data.input_amount,
                        potential_trade.fee,
                    )
                )  # eg. 16431450504869 token amount for 60000000000000000 (0.06) ETH
            else:
                trade_data.expected_amount = (
                    await self.protocol_manager.get_max_native_for_token(
                        potential_trade.token_address,
                        token_balance,
                        potential_trade.fee,
                    )
                )

            # Check if token amount is negative or invalid
            if trade_data.expected_amount < 0:
                # Handle the error or invalid token amount
                logging.error("Invalid token amount. Cannot proceed further.")
                return  # or raise an exception, return an error code, or take appropriate action

            if action == TradeAction.BUY:
                await self.buy_token(
                    potential_trade,
                    trade_data,
                    gas_fee,
                )
            elif action == TradeAction.SELL:
                self.sell_token(potential_trade, trade_data, gas_fee)
            else:
                raise ValueError(
                    "Invalid action. Use TradeAction.BUY or TradeAction.SELL."
                )

        except ValueError as error_message:
            logging.error(
                f"Error while simulating token trade {potential_trade.token_address}: \
                    {error_message}",
                exc_info=True,
            )
        except ConnectionError as error_message:
            logging.error(
                f"Connection error while simulating token trade \
                    {potential_trade.token_address}: {error_message}",
                exc_info=True,
            )

    async def buy_token(
        self, potential_trade: PotentialTrade, trade_data: TradeData, gas_fee
    ):
        logging.info(
            f"Buying token: {potential_trade.token_address}, input_amount: {trade_data.input_amount}, expected_amount: {trade_data.expected_amount}"
        )
        if self.demo_mode:
            # Calculate the net token amount after fees and slippage
            net_expected_token_amount = (
                calculate_estimated_net_token_amount_wei_after_fees(
                    potential_trade.fee, trade_data.expected_amount, 1
                )
            )

            # Calculate new balances after transaction
            new_eth_balance = (
                self.wallet_manager.get_native_token_balance()
                - trade_data.input_amount
                - gas_fee
            )
            new_token_balance = (
                self.wallet_manager.get_token_balance(
                    potential_trade.token_address.lower()
                )
                + net_expected_token_amount
            )

            # Set new balances
            self.wallet_manager.set_native_token_balance(new_eth_balance)
            self.wallet_manager.set_token_balance(
                potential_trade.token_address, int(new_token_balance)
            )
        else:
            # buys 0.1 worth of UNI with WETH
            # uniswap_client.make_trade(goerli_token1, goerli_token0, 100000000000000000)
            self.protocol_manager.make_trade(
                self.blockchain_manager.current_native_token_address,
                potential_trade.token_address,
                trade_data.input_amount,
                potential_trade.fee,
            )
        await self.token_monitor.add_monitored_token(potential_trade, trade_data)

    def sell_token(
        self, potential_trade: PotentialTrade, trade_data: TradeData, gas_fee
    ):
        logging.info(
            f"Selling token: {potential_trade.token_address}, input_amount: {trade_data.input_amount}, expected_amount: {trade_data.expected_amount}"
        )
        if self.demo_mode:
            # Convert the relevant values to Decimal
            # trade_amount = Decimal(trade_data.input_amount)
            expected_amount = Decimal(trade_data.expected_amount)  # in WETH/ETH/native
            gas_fee = Decimal(gas_fee)

            # Calculate new balances after transaction
            current_eth_balance = Decimal(
                self.wallet_manager.get_native_token_balance()
            )

            # Calculate the net token amount after fees and slippage, applies to WETH/ETH/native
            net_token_amount_wei = calculate_estimated_net_token_amount_wei_after_fees(
                potential_trade.fee, expected_amount, 1
            )

            new_token_balance = 0

            new_eth_balance = (current_eth_balance + net_token_amount_wei) - gas_fee

            logging.info(f"net_token_amount_wei: {net_token_amount_wei:.0f}")
            logging.info(f"new_eth_balance: {new_eth_balance:.0f}")
            logging.info(f"new_token_balance: {new_token_balance:.0f}")

            # Update balances
            self.wallet_manager.set_native_token_balance(int(new_eth_balance))
            self.wallet_manager.set_token_balance(
                potential_trade.token_address, int(new_token_balance)
            )
        else:
            # SELL
            self.protocol_manager.make_trade(
                potential_trade.token_address,
                self.blockchain_manager.current_native_token_address,
                trade_data.input_amount,
                potential_trade.fee,
            )
