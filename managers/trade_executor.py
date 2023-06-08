import logging
from decimal import Decimal

from attr import NOTHING

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.wallet_manager import WalletManager
from models.trade_action import TradeAction
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

    async def handle_trade(
        self,
        factory_address,
        token_address,
        pool_address,
        fee,
        native_token_address,
        trade_amount_wei,
        initial_token_amount,
        current_token_amount,
        action,
    ):
        await self.trade_token(
            factory_address,
            token_address,
            pool_address,
            native_token_address,
            fee,
            trade_amount_wei,
            initial_token_amount,
            current_token_amount,
            action,
        )

    async def trade_token(
        self,
        factory_address,
        token_address,
        pool_address,
        native_token_address,
        fee,
        trade_amount_wei,
        initial_token_amount,
        current_token_amount,
        action,
    ):
        try:
            gas_fee = self.blockchain_manager.calculate_gas_cost_wei(1)
            token_balance = self.wallet_manager.get_token_balance(
                token_address
            )  # balance for token in wallet

            if action == TradeAction.BUY:
                # amount of token for eth

                token_amount = await self.protocol_manager.get_min_token_for_native(
                    token_address, trade_amount_wei, fee
                )
            else:
                token_amount = await self.protocol_manager.get_max_native_for_token(
                    token_address, token_balance, fee
                )

            # Check if token amount is negative or invalid
            if token_amount < 0:
                # Handle the error or invalid token amount
                logging.error("Invalid token amount. Cannot proceed further.")
                return  # or raise an exception, return an error code, or take appropriate action

            if action == TradeAction.BUY:
                self.buy_token(token_address, trade_amount_wei, token_amount, gas_fee)
            elif action == TradeAction.SELL:
                self.sell_token(
                    token_address, fee, trade_amount_wei, token_amount, gas_fee
                )
            else:
                raise ValueError(
                    "Invalid action. Use TradeAction.BUY or TradeAction.SELL."
                )

            await self.token_monitor.add_monitored_token(
                factory_address,
                token_address,
                pool_address,
                native_token_address,
                fee,
                initial_token_amount,
                current_token_amount,
                trade_amount_wei,
            )
        except ValueError as error_message:
            logging.error(
                f"Error while simulating token trade {token_address}: \
                    {error_message}",
                exc_info=True,
            )
        except ConnectionError as error_message:
            logging.error(
                f"Connection error while simulating token trade \
                    {token_address}: {error_message}",
                exc_info=True,
            )

    def buy_token(self, token_address, trade_amount, token_amount, gas_fee):
        logging.info(
            f"Buying token: {token_address}, trade_amount: {trade_amount}, token_amount: {token_amount}"
        )
        if self.demo_mode:
            slippage_tolerance = 0.01

            # Convert token amount to DAI (or the token's native unit)
            # token_decimals = 18  # Assuming DAI has 18 decimals
            # token_amount_dai = token_amount / 10**token_decimals

            # Apply slippage tolerance and convert back to Wei
            net_token_amount = int(token_amount * (1 - slippage_tolerance))

            # Calculate new balances after transaction
            new_eth_balance = (
                self.wallet_manager.get_native_token_balance() - trade_amount - gas_fee
            )
            new_token_balance = (
                self.wallet_manager.get_token_balance(token_address.lower())
                + net_token_amount
            )

            # Set new balances
            self.wallet_manager.set_native_token_balance(new_eth_balance)
            self.wallet_manager.set_token_balance(token_address, new_token_balance)
        else:
            self.protocol_manager.make_trade(
                self.blockchain_manager.current_native_token_address,
                token_address,
                trade_amount,
            )

    def sell_token(self, token_address, fee, trade_amount, token_amount, gas_fee):
        logging.info(
            f"Selling token: {token_address}, trade_amount: {trade_amount}, token_amount: {token_amount}"
        )
        if self.demo_mode:
            # Convert the relevant values to Decimal
            trade_amount = Decimal(trade_amount)
            token_amount = Decimal(token_amount)
            gas_fee = Decimal(gas_fee)

            # Calculate new balances after transaction
            current_eth_balance = Decimal(
                self.wallet_manager.get_native_token_balance()
            )

            # Calculate the net token amount after fees and slippage
            net_token_amount_wei = calculate_estimated_net_token_amount_wei_after_fees(
                fee, token_amount, 1
            )

            new_token_balance = 0

            new_eth_balance = (current_eth_balance + net_token_amount_wei) - gas_fee

            logging.info(f"net_token_amount_wei: {net_token_amount_wei:.0f}")
            logging.info(f"new_eth_balance: {new_eth_balance:.0f}")
            logging.info(f"new_token_balance: {new_token_balance:.0f}")

            # Update balances
            self.wallet_manager.set_native_token_balance(int(new_eth_balance))
            self.wallet_manager.set_token_balance(token_address, int(new_token_balance))
        else:
            self.protocol_manager.make_trade_output(
                token_address,
                self.blockchain_manager.current_native_token_address,
                trade_amount,
            )
