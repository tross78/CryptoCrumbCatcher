import asyncio
import json

from logger_config import logger
from models.defi_structures import Fee, Pool, Token
from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor


class TokenStatusManager:
    def __init__(self, token_analysis: TokenAnalysis, token_monitor: TokenMonitor):
        # Initialize TokenStatusManager with instances of TokenAnalysis and TokenMonitor
        self.token_analysis: TokenAnalysis = token_analysis
        self.token_monitor: TokenMonitor = token_monitor
        concurrent_limit = 20
        self.semaphore = asyncio.Semaphore(concurrent_limit)
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
        logger.info(f"Cleared tasks.")

        # Iterates over new_tokens, which is expected to be a list of dictionaries with keys 'token', 'pool_address', and 'fee'
        for token_index, token_info in enumerate(new_tokens):
            try:  # Try to create a task for this token
                token: Token = token_info["token"]
                pool: Pool = token_info["pool"]
                fee: Fee = token_info["fee"]

                # Creates a unique identifier for each token by concatenating token address and pool address
                token_pool_id = f"{token.id}_{pool.id}"

                # logger.info(f"Processing token: {token_pool_id}")

                # Checks if the token is already being monitored, if so it skips to the next token
                if token_pool_id in self.token_monitor.get_monitored_tokens():
                    logger.info(f"Token already monitored: {token_pool_id}")
                    continue

                logger.info(
                    f"Checking tokensniffer score of token {token.id}. {token_index} of {len(new_tokens)}"
                )
                # Checks if the token has any exploits, and if the token is not already being monitored
                token_passes_muster = not await self.token_analysis.has_exploits(
                    token.id
                )
                token_has_no_task = token_pool_id not in self.tokens_with_tasks

                # If the token has no exploits and is not being monitored, it creates a task to check if the token's price is increasing
                if token_passes_muster and token_has_no_task:
                    logger.info(f"Creating async task for token {token.id}")
                    task = None
                    async with self.semaphore:
                        task = asyncio.create_task(
                            self.token_analysis.is_token_price_increase(
                                token, fee, pool
                            )
                        )

                    # Appends the task and token data to self.tasks and adds the token_pool_id to self.tokens_with_tasks
                    if task:
                        self.tasks.append((task, token, fee, pool))
                        self.tokens_with_tasks.add(token_pool_id)

            except Exception as e:
                logger.error(f"Failed to create task for token {token_info}: {e}")
                continue

        # Returns the list of tasks and the set of tokens_with_tasks
        logger.info(f"Returning tasks and tokens_with_tasks.")
        return self.tasks, self.tokens_with_tasks
