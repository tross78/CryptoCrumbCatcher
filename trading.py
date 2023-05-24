import logging
from trade_action import TradeAction
from token_analysis import TokenAnalysis
from collections import deque
import json
from web3 import Web3
from decimal import Decimal


class Trading:

    def __init__(self, data_manager, token_analysis, demo_mode=True):
        self.demo_mode = demo_mode
        self.data_manager = data_manager
        self.token_analysis: TokenAnalysis = token_analysis
        self.monitored_token_threads = {}  # Store the token threads in a dictionary

    def break_even_roi(self, initial_investment, num_transactions=2):
        gas_limit_per_transaction = 150000  # Example gas limit per transaction
        # Get the current gas price in Gwei
        gas_price_gwei = self.data_manager.w3.eth.gas_price
        gas_cost_per_transaction_weth = Web3.from_wei(
            gas_price_gwei * gas_limit_per_transaction, 'ether')
        total_gas_fees = gas_cost_per_transaction_weth * num_transactions
        break_even = Decimal(initial_investment) + total_gas_fees
        return break_even

    def calculate_roi(self):
        initial_investment = Decimal(self.data_manager.trade_amount_eth)
        break_even = self.break_even_roi(initial_investment)
        desired_profit_percentage = Decimal('0.1')  # Desired profit 10%
        desired_profit_value = break_even * desired_profit_percentage
        expected_roi_value = break_even + desired_profit_value
        expected_roi_multiplier = expected_roi_value / initial_investment
        logging.info(
            f'Initial investment: {initial_investment} Break even: {break_even} Profit percentage: {desired_profit_percentage} Multiplier: {expected_roi_multiplier}')
        return expected_roi_multiplier

    def monitor_and_buy_from_watchlist(
        self,
        factory_address,
        native_token_address,
        native_token_trade_amount,
        watchlist,
    ):
        watchlist_copy = deque(watchlist)  # Make a copy of the watchlist
        for token in watchlist_copy:
            token_address = token["token_address"]
            if not any(
                obj["token_address"] == token_address
                for obj in self.data_manager.data["monitored_tokens"]
            ):
                pool = token["pool"]
                initial_token_price = token["initial_price"]
                current_token_price = self.data_manager.get_min_token_for_native(
                    token_address, self.data_manager.trade_amount_wei, pool
                )

                if (
                    current_token_price
                    >= float(initial_token_price) * self.token_analysis.PRICE_INCREASE_THRESHOLD
                ):
                    if self.has_balance_for_trade(
                        token_address, native_token_trade_amount, TradeAction.BUY
                    ):
                        if self.demo_mode:
                            self.trade_token_demo(
                                token_address,
                                pool,
                                native_token_trade_amount,
                                TradeAction.BUY,
                            )
                        else:
                            self.trade_token(
                                token_address, pool, native_token_trade_amount
                            )

                        buy_price = token[
                            "buy_price"
                        ] = current_token_price  # Store the buy price of the token
                        self.add_monitored_token(
                            factory_address,
                            token_address,
                            native_token_address,
                            native_token_trade_amount,
                            pool,
                            buy_price,
                            initial_token_price,
                        )
                    else:
                        logging.info(
                            f"No balance left to trade {token_address}, removing from watchlist."
                        )
                        watchlist.remove(token)

    def monitor_and_sell(self):
        monitored_tokens = self.data_manager.data["monitored_tokens"][:]

        for token in monitored_tokens:
            token_address = token["token_address"]
            pool = token["pool"]
            buy_price = token.get("buy_price", 0)

            current_price = self.data_manager.get_min_token_for_native(
                token_address, 1000000000000000, pool
            )

            current_roi_multiplier = current_price / buy_price if buy_price > 0 else 0

            price_decrease_ratio = buy_price / current_price if current_price > 0 else 1
            expected_roi_multiplier = self.calculate_roi()

            logging.info(
                f'Current ROI Multiplier: {current_roi_multiplier} Expected ROI Multiplier: {expected_roi_multiplier}')

            if (
                current_roi_multiplier >= expected_roi_multiplier
                or price_decrease_ratio <= self.token_analysis.PRICE_DECREASE_THRESHOLD
            ):
                logging.info(
                    f"Token {token_address} sold due to {'reaching desired ROI' if current_roi_multiplier >= expected_roi_multiplier else 'price decrease'}."
                )
                if not self.get_wallet_tokens().get(token_address):
                    logging.info(
                        f"{token_address} is not in the token balance dictionary. Removing token {token_address} from monitored tokens"
                    )
                    self.remove_monitored_token(token_address)
                else:
                    token_balance = self.get_wallet_token_balance(
                        token_address)
                    native_token_amount = self.data_manager.get_min_token_for_native(
                        token_address, token_balance, pool)
                    if self.has_balance_for_trade(
                        token_address, native_token_amount, TradeAction.SELL
                    ):
                        self.trade_token_demo(
                            token_address, pool, native_token_amount, TradeAction.SELL
                        )
                        self.remove_monitored_token(token_address)

    def has_balance_for_trade(self, token_address, trade_amount, action):
        estimated_gas_limit = 150000
        num_trades = 2  # Number of trades to consider

        # Get the average gas price in Gwei
        average_gas_price = self.data_manager.w3.eth.gas_price
        gas_fee = average_gas_price * estimated_gas_limit * num_trades

        if action == TradeAction.BUY:
            native_token_balance = self.get_wallet_token_balance(
                self.data_manager.get_selected_chain().native_token_address)
            if native_token_balance < trade_amount + gas_fee:
                logging.info(
                    "Not enough Native Token balance to make the trade.")
                return False
        elif action == TradeAction.SELL:
            if token_address not in self.get_wallet_tokens():
                logging.info(
                    f"{token_address} is not in the token balance dictionary.")
                return False
            token_balance = self.get_wallet_token_balance(token_address)
            if token_balance < trade_amount:
                logging.info(
                    f"Not enough {token_address} tokens balance to make the trade.")
                return False

        return True

    def trade_token_demo(self, token_address, pool, trade_amount, action):
        try:
            gas_fee = self.calculate_gas_fee()
            token_balance = self.get_wallet_token_balance(token_address)
            token_amount = self.data_manager.get_min_token_for_native(
                token_address, trade_amount if action == TradeAction.BUY else token_balance, pool)

            if action == TradeAction.BUY:
                self.buy_token(token_address, pool,
                               trade_amount, token_amount, gas_fee)
            elif action == TradeAction.SELL:
                self.sell_token(token_address, pool,
                                trade_amount, token_amount, gas_fee)
            else:
                raise ValueError(
                    "Invalid action. Use TradeAction.BUY or TradeAction.SELL.")
        except Exception as e:
            logging.error(
                f"Error while simulating token trade {token_address}: {e}", exc_info=True)

    def calculate_gas_fee(self):
        average_gas_price = self.data_manager.w3.eth.gas_price
        estimated_gas_limit = 150000
        gas_fee = average_gas_price * estimated_gas_limit
        return gas_fee

    def get_wallet_token_balance(self, token_address):
        selected_chain = self.data_manager.get_selected_chain()
        # Checking if token_address exists in the tokens
        if token_address.lower() not in self.data_manager.data["demo_balance"][selected_chain.name]["tokens"]:
            logging.error(
                f"Token address {token_address} not found in the tokens")
            return
        wallet_token_balance = self.data_manager.data["demo_balance"][selected_chain.name]["tokens"].get(
            token_address.lower(), 0)
        logging.info(
            f'Wallet token {token_address} balance: {wallet_token_balance}')
        return

    def get_wallet_tokens(self):
        selected_chain = self.data_manager.get_selected_chain()
        # Checking if selected_chain.name exists in the data
        if selected_chain.name not in self.data_manager.data["demo_balance"]:
            logging.error(
                f"Chain name {selected_chain.name} not found in the data")
            return
        wallet_tokens = self.data_manager.data["demo_balance"][selected_chain.name]["tokens"]
        logging.info(f'Wallet tokens: {wallet_tokens}')
        return wallet_tokens

    def update_wallet_balance(self, native_token_amount, token_address, token_amount):
        try:
            native_token_address = self.data_manager.get_selected_chain().native_token_address
            selected_chain = self.data_manager.get_selected_chain()

            # Checking if selected_chain.name exists in the data
            if selected_chain.name not in self.data_manager.data["demo_balance"]:
                logging.error(
                    f"Chain name {selected_chain.name} not found in the data")
                return

            # Checking if native_token_address exists in the tokens
            if native_token_address.lower() not in self.data_manager.data["demo_balance"][selected_chain.name]["tokens"]:
                logging.error(
                    f"Native token address {native_token_address} not found in the tokens")
                return

            # Checking if token_address exists in the tokens
            if token_address.lower() not in self.data_manager.data["demo_balance"][selected_chain.name]["tokens"]:
                logging.error(
                    f"Token address {token_address} not found in the tokens")
                return

            self.data_manager.data["demo_balance"][selected_chain.name]["tokens"][native_token_address.lower(
            )] += native_token_amount
            self.data_manager.data["demo_balance"][selected_chain.name]["tokens"][token_address.lower(
            )] = token_amount
            with open("demo_balance.json", "w") as json_file:
                json.dump(self.data_manager.data["demo_balance"], json_file)

            logging.info("Wallet balance updated successfully")
        except Exception as e:
            logging.error(
                f"An error occurred while updating wallet balance: {str(e)}", exc_info=True)

    def buy_token(self, token_address, pool, trade_amount, token_amount, gas_fee):
        slippage_tolerance = 0.01
        net_token_amount = token_amount * (1 - slippage_tolerance)
        net_token_amount_wei = self.data_manager.w3.to_wei(
            net_token_amount, "ether")

        new_native_token_amount = -trade_amount - gas_fee
        new_token_amount = self.get_wallet_token_balance(
            token_address) + net_token_amount_wei

        self.update_wallet_balance(
            new_native_token_amount, token_address, new_token_amount)

    def sell_token(self, token_address, pool, trade_amount, token_amount, gas_fee):
        fee_percentage = self.data_manager.get_pool_fee(pool) / 1000000
        slippage_tolerance = 0.01

        net_token_amount = token_amount * \
            (1 - fee_percentage) * (1 - slippage_tolerance)
        net_token_amount_wei = self.data_manager.w3.to_wei(
            net_token_amount, "ether")

        new_native_token_amount = net_token_amount_wei - gas_fee
        new_token_amount = self.get_wallet_token_balance(
            token_address) - trade_amount

        self.update_wallet_balance(
            new_native_token_amount, token_address, new_token_amount)

    def add_monitored_token(
        self,
        factory_address,
        token_address,
        native_token_address,
        native_token_trade_amount,
        pool,
        buy_price,
        initial_price,
    ):
        monitored_tokens = self.data_manager.data["monitored_tokens"]
        if not any(obj["token_address"] == token_address for obj in monitored_tokens):
            monitored_tokens.append(
                {
                    "token_address": token_address,
                    "factory_address": factory_address,
                    "native_token_address": native_token_address,
                    "native_token_trade_amount": native_token_trade_amount,
                    "pool": pool,
                    "buy_price": buy_price,
                    "initial_price": initial_price,
                }
            )
            logging.info(f"Token {token_address} added to monitored tokens.")
            # Save the updated list of monitored tokens
            with open("monitored_tokens.json", "w") as json_file:
                json.dump(monitored_tokens, json_file)
        else:
            logging.info(
                f"Token {token_address} is already in monitored tokens.")

    def remove_monitored_token(self, token_address):
        # Remove the object with the matching "token" element
        self.data_manager.data["monitored_tokens"] = [
            obj
            for obj in self.data_manager.data["monitored_tokens"]
            if obj["token_address"] != token_address
        ]

        # Stop the monitoring thread for the token
        if token_address in self.monitored_token_threads:
            thread, stop_event = self.monitored_token_threads[token_address]
            stop_event.set()  # Signal the monitoring thread to stop
            thread.join()  # Wait for the thread to finish
            del self.monitored_token_threads[
                token_address
            ]  # Remove the thread from the dictionary

        # Save the updated list of monitored tokens
        with open("monitored_tokens.json", "w") as json_file:
            json.dump(self.data_manager.data["monitored_tokens"], json_file)

    def get_best_token_price(self, watchlist):
        best_token_price = 0
        best_token = None
        for token in watchlist:
            token_address = token["token_address"]
            pool = token["pool"]
            token_price = self.data_manager.get_max_native_for_token(
                token_address, self.data_manager.trade_amount_wei, pool)
            if token_price > best_token_price:
                best_token_price = token_price
                best_token = token
        return best_token_price, best_token
