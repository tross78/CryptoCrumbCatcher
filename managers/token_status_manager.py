import asyncio
import json
import logging

from token_info.token_analysis import TokenAnalysis
from token_info.token_monitor import TokenMonitor


class TokenStatusManager:
    def __init__(self, token_analysis: TokenAnalysis, token_monitor: TokenMonitor):
        self.token_analysis: TokenAnalysis = token_analysis
        self.token_monitor: TokenMonitor = token_monitor
        self.tasks = []
        self.tokens_with_tasks = set()

    def get_tasks(self):
        return self.tasks

    def get_tokens_with_tasks(self):
        return self.tokens_with_tasks

    async def create_token_check_tasks(self, new_tokens):
        self.tasks.clear()  # Clear the tasks list
        for token_info in new_tokens:
            token_address = token_info["token"]
            pool_address = token_info["pool_address"]
            fee = token_info["fee"]

            # Use a combination of the token address and the pool address as a unique identifier
            token_pool_id = f"{token_address}_{pool_address}"

            # Check if token is already being monitored
            # if so, don't waste checking
            if token_pool_id in self.token_monitor.get_monitored_tokens():
                continue

            token_passes_muster = not self.token_analysis.has_exploits(token_address)
            token_has_no_task = token_pool_id not in self.tokens_with_tasks
            # logging.info(
            #     f"token {token_address} in pool {pool_address} \
            #         passes basic exploit test: {token_passes_muster}"
            # )
            # logging.info(
            #     f"token {token_address} in pool {pool_address} \
            #         does not have a running task: {token_has_no_task}"
            # )

            if token_passes_muster and token_has_no_task:
                task = asyncio.create_task(
                    self.token_analysis.is_token_price_increase(
                        token_address, fee, pool_address
                    )
                )

                self.tasks.append((task, token_address, fee, pool_address))
                self.tokens_with_tasks.add(token_pool_id)

                logging.info(
                    f"Created price increase check task for token {token_address} in pool {pool_address}."
                )

                # Yield control back to the event loop after each task is created
                await asyncio.sleep(5)

        return self.tasks, self.tokens_with_tasks
