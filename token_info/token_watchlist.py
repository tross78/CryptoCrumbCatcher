"""
A class used to manage a watchlist of tokens.
"""
import json
import logging

from managers.blockchain_manager import BlockchainManager


class TokenWatchlist:
    def __init__(self, max_tokens, blockchain_manager: BlockchainManager):
        self.tokens = {}
        self.max_tokens = max_tokens
        self.blockchain_manager = blockchain_manager
        self.load_from_file()

    def __iter__(self):
        current_chain = self.blockchain_manager.get_current_chain().name
        for token in self.tokens.get(current_chain, {}):
            yield self.tokens[current_chain][token]

    def __len__(self):
        current_chain = self.blockchain_manager.get_current_chain().name
        return len(self.tokens.get(current_chain, {}))

    async def update(self, tasks_with_infos):
        logging.info(
            f"Updating watchlist with {len(tasks_with_infos)} tasks. Current watchlist token count: {len(self)}"
        )

        for task_info in tasks_with_infos:
            task, token_address, fee, pool_address = task_info
            try:
                result = task.result()  # Get the result from the already completed task
            except Exception as error_message:
                logging.error(
                    f"Error while running task: {error_message}. Task info: {task_info}"
                )
                continue

            if result:
                try:
                    if not self.is_duplicate(token_address, pool_address):
                        (price_has_increased, initial_token_amount) = result
                        # if price_has_increased:
                        self.add(token_address, fee, pool_address, initial_token_amount)
                except Exception as error_message:
                    logging.error(
                        f"Error while processing task result: {error_message}. Task info: {task_info}"
                    )
                    continue

    def add(self, token_address, fee, pool_address, initial_token_amount):
        current_chain = self.blockchain_manager.get_current_chain().name
        if (
            not self.is_duplicate(token_address, pool_address)
            and len(self.tokens.get(current_chain, {})) < self.max_tokens
        ):
            gas_limit_per_transaction = (
                self.blockchain_manager.gas_limit_per_transaction
            )
            # Get the current gas price in Gwei
            gas_price_wei = self.blockchain_manager.web3_instance.eth.gas_price
            total_transaction_gas_price_wei = (
                gas_price_wei * gas_limit_per_transaction * 2
            )

            token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
            if (
                current_chain not in self.tokens
                and initial_token_amount
                > total_transaction_gas_price_wei  # weeds out errored price calls
            ):
                self.tokens[current_chain] = {}
                # add token dict
            self.tokens[current_chain][token_pool_id] = {
                "token_address": token_address.lower(),
                "fee": fee,
                "pool_address": pool_address.lower(),
                "initial_token_amount": initial_token_amount,
            }

            logging.info(f"Token {token_address} added to watchlist.")
            self.save_to_file()

    def remove(self, token_address, pool_address):
        current_chain = self.blockchain_manager.get_current_chain().name
        token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"

        if current_chain in self.tokens and token_pool_id in self.tokens[current_chain]:
            logging.info(f"Deleting Token {token_address} from watchlist")
            del self.tokens[current_chain][token_pool_id]
            self.save_to_file()
        else:
            logging.info(
                f"Token {token_address} not found in the watchlist for the {current_chain} chain."
            )

    def is_duplicate(self, token_address, pool_address):
        current_chain = self.blockchain_manager.get_current_chain().name
        token_pool_id = f"{token_address.lower()}_{pool_address.lower()}"
        return token_pool_id in self.tokens.get(current_chain, {})

    def has_token_address(self, token_address):
        current_chain = self.blockchain_manager.get_current_chain().name

        for token_data in self.tokens.get(current_chain, {}).values():
            if token_data["token_address"] == token_address:
                return True

        return False

    def set_tokens(self, tokens):
        current_chain = self.blockchain_manager.get_current_chain().name
        self.tokens[current_chain] = tokens
        self.save_to_file()

    def load_from_file(self):
        try:
            with open("data/watchlist.json", "r") as json_file:
                self.tokens = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            # File does not exist or invalid JSON. Initialize an empty dict.
            self.tokens = {}

    def save_to_file(self):
        with open("data/watchlist.json", "w") as json_file:
            json.dump(self.tokens, json_file)
