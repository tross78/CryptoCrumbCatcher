import asyncio
import json
import logging

from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor


class TokenStatusManager:
    def __init__(self, token_analysis: TokenAnalysis, token_monitor: TokenMonitor):
        # Initialize TokenStatusManager with instances of TokenAnalysis and TokenMonitor
        self.token_analysis: TokenAnalysis = token_analysis
        self.token_monitor: TokenMonitor = token_monitor
        # tasks stores tuples containing asyncio tasks and token data
        self.tasks = []
        # tokens_with_tasks is a set of token_pool_id strings representing tokens already being monitored
        self.tokens_with_tasks = set()

    def get_tasks(self):
        # Returns list of tasks
        return self.tasks

    def get_tokens_with_tasks(self):
        # Returns set of tokens that are currently being monitored
        return self.tokens_with_tasks

    async def create_token_check_tasks(self, new_tokens):
        # Clears the tasks list
        self.tasks.clear()
        logging.info(f"Cleared tasks.")

        # Iterates over new_tokens, which is expected to be a list of dictionaries with keys 'token', 'pool_address', and 'fee'
        for token_info in new_tokens:
            token_address = token_info["token"]
            pool_address = token_info["pool_address"]
            fee = token_info["fee"]
            # Creates a unique identifier for each token by concatenating token address and pool address
            token_pool_id = f"{token_address}_{pool_address}"

            logging.info(f"Processing token: {token_pool_id}")

            # Checks if the token is already being monitored, if so it skips to the next token
            if token_pool_id in self.token_monitor.get_monitored_tokens():
                logging.info(f"Token already monitored: {token_pool_id}")
                continue

            # Checks if the token has any exploits, and if the token is not already being monitored
            token_passes_muster = not await self.token_analysis.has_exploits(
                token_address
            )
            token_has_no_task = token_pool_id not in self.tokens_with_tasks

            logging.info(
                f"Token passes muster: {token_passes_muster}, Token has no task: {token_has_no_task}"
            )

            # If the token has no exploits and is not being monitored, it creates a task to check if the token's price is increasing
            if token_passes_muster and token_has_no_task:
                task = asyncio.create_task(
                    self.token_analysis.is_token_price_increase(
                        token_address, fee, pool_address
                    )
                )

                # Appends the task and token data to self.tasks and adds the token_pool_id to self.tokens_with_tasks
                self.tasks.append((task, token_address, fee, pool_address))
                self.tokens_with_tasks.add(token_pool_id)

                logging.info(
                    f"Created price increase check task for token {token_address} in pool {pool_address}."
                )

                # Sleeps for 5 seconds after creating each task
                await asyncio.sleep(5)

        # Returns the list of tasks and the set of tokens_with_tasks
        logging.info(f"Returning tasks and tokens_with_tasks.")
        return self.tasks, self.tokens_with_tasks
