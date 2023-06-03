import json
import logging


class TokenMonitor:
    def __init__(self, selected_chain_name, reset_userdata_on_load):
        self.reset_userdata_on_load = reset_userdata_on_load
        self.tokens = self.load_monitored_tokens()
        self.selected_chain_name = selected_chain_name

    def get_monitored_tokens(self):
        return self.tokens.setdefault(self.selected_chain_name, {})

    def set_monitored_tokens(self, monitored_tokens):
        self.tokens[self.selected_chain_name] = monitored_tokens
        self.save_monitored_tokens()

    def load_monitored_tokens(self):
        if self.reset_userdata_on_load:
            self.tokens = {"ethereum_mainnet": {}, "arbitrum_mainnet": {}}
            self.save_monitored_tokens()
        with open("data/monitored_tokens.json", "r") as json_file:
            return json.load(json_file)

    def save_monitored_tokens(self):
        with open("data/monitored_tokens.json", "w") as json_file:
            json.dump(self.tokens, json_file)

    def is_duplicate(self, token_address, pool_address):
        token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
        monitored_tokens = self.get_monitored_tokens()
        return any(
            f'{obj["token_address"]}_{obj["pool_address"]}' == token_pool_id
            for obj in monitored_tokens.values()
        )

    def has_token_address(self, token_address):
        for token_data in self.tokens.get(self.selected_chain_name, {}).values():
            if token_data["token_address"] == token_address:
                return True

        return False

    def add_monitored_token(
        self,
        factory_address,
        token_address,
        pool_address,
        native_token_address,
        native_token_trade_amount,
        fee,
        initial_token_amount,
    ):
        monitored_tokens = self.get_monitored_tokens()
        if not self.is_duplicate(token_address, pool_address):
            token_pool_id = f"{token_address}_{pool_address}"
            monitored_tokens[token_pool_id] = {
                "factory_address": factory_address,
                "token_address": token_address.lower(),
                "native_token_address": native_token_address,
                "native_token_trade_amount": native_token_trade_amount,
                "fee": fee,
                "pool_address": pool_address.lower(),
                "initial_token_amount": initial_token_amount,
            }
            logging.info(f"Token {token_address} added to monitored tokens.")
            # Save the updated dictionary of monitored tokens
            self.save_monitored_tokens()
        else:
            logging.info(f"Token {token_address} is already in monitored tokens.")

    def remove_monitored_token(self, token_address, pool_address):
        # Remove the object with the matching "token_address" and "pool_address" combination
        monitored_tokens = self.get_monitored_tokens()
        removed_tokens = [
            key
            for key, obj in monitored_tokens.items()
            if obj["token_address"] == token_address
            and obj["pool_address"] == pool_address
        ]
        for token_key in removed_tokens:
            del monitored_tokens[token_key]

        # Save the updated dictionary of monitored tokens
        self.save_monitored_tokens()
