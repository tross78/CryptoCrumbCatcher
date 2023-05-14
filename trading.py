from trade_action import TradeAction
from token_analysis import TokenAnalysis
from collections import deque
import json


class Trading:

    DESIRED_ROI = 2  # 2x

    def __init__(self, data_manager, token_analysis, demo_mode=True):
        self.demo_mode = demo_mode
        self.data_manager = data_manager
        self.token_analysis: TokenAnalysis = token_analysis
        self.monitored_token_threads = {}  # Store the token threads in a dictionary

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
                current_token_price = self.data_manager.get_native_token_output_price(
                    token_address, 1000000000000000, pool
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
                        print(
                            f"No balance left to trade {token_address}, removing from watchlist."
                        )
                        watchlist.remove(token)

    def monitor_and_sell(self, best_token_price):
        # Sell tokens that reached the desired ROI or have decreased in price by a certain threshold
        for token in self.data_manager.data["monitored_tokens"]:
            token_address = token["token_address"]
            pool = token["pool"]
            buy_price = token.get("buy_price", 0)
            roi = best_token_price / buy_price if buy_price > 0 else 0
            price_decrease_ratio = best_token_price / buy_price if buy_price > 0 else 1

            if (
                roi >= self.DESIRED_ROI
                or price_decrease_ratio <= self.token_analysis.PRICE_DECREASE_THRESHOLD
            ):
                print(
                    f"Token {token_address} sold due to {'reaching desired ROI' if roi >= self.DESIRED_ROI else 'price decrease'}."
                )
                if (
                    token_address
                    not in self.get_wallet_tokens()
                ):
                    print(
                        f"{token_address} is not in the token balance dictionary. Removing token {token_address} from monitored tokens"
                    )
                    self.remove_monitored_token(token_address)
                    return
                token_balance = self.get_wallet_token_balance(token_address)
                native_token_amount = self.data_manager.get_native_token_output_price(token_address, token_balance, pool)
                if self.has_balance_for_trade(
                    token_address, native_token_amount, TradeAction.SELL
                ):
                    self.trade_token_demo(
                        token_address, pool, native_token_amount, TradeAction.SELL
                    )
                    self.remove_monitored_token(token_address)

    def has_balance_for_trade(self, token_address, trade_amount, action):
        # You can adjust this based on your experience with Uniswap transactions
        estimated_gas_limit = 150000
        # Get the average gas price in Gwei
        average_gas_price = self.data_manager.w3.eth.gas_price
        gas_fee = average_gas_price * estimated_gas_limit
        # action_str = "action equals enum BUY or SELL" if action == TradeAction.BUY or TradeAction.SELL else "action not correct format"
        print(
            f"Token: {token_address}, Trade amount: {trade_amount}, Action: {action}, Gas fee: {gas_fee}"
        )

        if action == TradeAction.BUY:
            if (self.get_wallet_token_balance(self.data_manager.get_selected_chain().native_token_address) < trade_amount + gas_fee):
                print("Not enough Native Token balance to make the trade.")
                return False
            else:
                return True
        if action == TradeAction.SELL:
            if token_address not in self.get_wallet_tokens():
                print(f"{token_address} is not in the token balance dictionary.")
                return False
            if (
                self.get_wallet_token_balance(token_address) < trade_amount):
                print(
                    f"Not enough {token_address} tokens balance to make the trade.")
                return False
            else:
                return True

    def trade_token_demo(self, token_address, pool, trade_amount, action):
        try:
            gas_fee = self.calculate_gas_fee()
            token_balance = self.get_wallet_token_balance(self, token_address)
            token_amount = self.data_manager.get_native_token_output_price(token_address, trade_amount if action == TradeAction.BUY else token_balance, pool)

            if action == TradeAction.BUY:
                self.buy_token(token_address, pool, trade_amount, token_amount, gas_fee)
            elif action == TradeAction.SELL:
                self.sell_token(token_address, pool, trade_amount, token_amount, gas_fee)
            else:
                raise ValueError("Invalid action. Use TradeAction.BUY or TradeAction.SELL.")
        except Exception as e:
            print(f"Error while simulating token trade {token_address}: {e}")

    def calculate_gas_fee(self):
        average_gas_price = self.data_manager.w3.eth.gas_price
        estimated_gas_limit = 150000
        gas_fee = average_gas_price * estimated_gas_limit
        return gas_fee

    def get_wallet_token_balance(self, token_address):
        return self.data_manager.data["demo_balance"]["tokens"].get(token_address.lower(), 0)
    
    def get_wallet_tokens(self):
        return self.data_manager.data["demo_balance"]["tokens"]

    def update_wallet_balance(self, native_token_amount, token_address, token_amount):
        native_token_address = self.data_manager.get_selected_chain().native_token_address
        self.data_manager.data["demo_balance"]["tokens"][native_token_address.lower()] += native_token_amount
        self.data_manager.data["demo_balance"]["tokens"][token_address.lower()] = token_amount
        with open("demo_balance.json", "w") as json_file:
            json.dump(self.data_manager.data["demo_balance"], json_file)

    def buy_token(self, token_address, pool, trade_amount, token_amount, gas_fee):
        slippage_tolerance = 0.01
        net_token_amount = token_amount * (1 - slippage_tolerance)
        net_token_amount_wei = int(net_token_amount * (10 ** 18))

        new_native_token_amount = -trade_amount - gas_fee
        new_token_amount = self.get_wallet_token_balance(token_address) + net_token_amount_wei

        self.update_wallet_balance(new_native_token_amount, token_address, new_token_amount)

    def sell_token(self, token_address, pool, trade_amount, token_amount, gas_fee):
        fee_percentage = int(pool["feeTier"]) / 1000000
        slippage_tolerance = 0.01

        net_token_amount = token_amount * (1 - fee_percentage) * (1 - slippage_tolerance)
        net_token_amount_wei = int(net_token_amount * (10 ** 18))

        new_native_token_amount = net_token_amount_wei - gas_fee
        new_token_amount = self.get_wallet_token_balance(token_address) - trade_amount

        self.update_wallet_balance(new_native_token_amount, token_address, new_token_amount)

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
        if token_address not in self.data_manager.data["monitored_tokens"]:
            self.data_manager.data["monitored_tokens"].append(
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
            print(f"Token {token_address} added to monitored tokens.")
        else:
            print(f"Token {token_address} is already in monitored tokens.")

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
        # Get the highest valued token from watchlist
        best_token_price = 0
        for token in watchlist:
            token_address = token["token_address"]
            pool = token["pool"]
            token_price = self.data_manager.get_token_native_output_price(
                token_address, 1000000000000000, pool
            )
            if token_price > best_token_price:
                best_token_price = token_price
        return best_token_price
