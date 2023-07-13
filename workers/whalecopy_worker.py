import asyncio

from logger_config import logger
from workers import ChainWorker


class WhaleCopyWorker(ChainWorker):
    async def work_on_chain(self, stdscr):
        all_tasks = set()
        await self.watchlist.load_from_file()
        while True:
            current_bot_chain = (
                self.bot_controller.blockchain_manager.get_current_chain()
            )
            print(f"Working on chain: {current_bot_chain.name}")
            try:
                new_tokens = await self.get_whale_buy_tokens()
                logger.info(f"New tokens: {new_tokens}")

                price_check_tasks = await self.perform_token_checks(new_tokens)

                all_tasks.update(price_check_tasks)

                update_task, monitor_trades_task = await self.update_and_monitor_trades(
                    all_tasks, price_check_tasks
                )
                all_tasks.add(update_task)
                all_tasks.add(monitor_trades_task)

                await self.process_task_results(all_tasks, monitor_trades_task)
            except Exception as error:
                logger.exception(f"Error in main loop: {error}", exc_info=True)

            if all(task.done() for task in all_tasks):
                print(f"Finished working on chain: {current_bot_chain.name}")
                selected_chain = next(self.selected_chains)
                self.bot_controller.blockchain_manager.set_current_chain(selected_chain)
                self.bot_controller.blockchain_manager.set_provider()

    async def perform_token_checks(self, new_tokens):
        (
            price_check_tasks,
            tokens_with_check_tasks,
        ) = await self.token_status_manager.create_token_check_tasks(new_tokens)

        logger.info(f"Price check tasks: {price_check_tasks}")
        logger.info(f"Tokens with check tasks: {tokens_with_check_tasks}")

        tasks_only = [task for task, _, _, _ in price_check_tasks]
        # Wait for all price check tasks to complete
        results = await asyncio.gather(*tasks_only, return_exceptions=True)

        for task_result in results:
            if isinstance(task_result, Exception):
                logger.error(f"Error in price check task: {task_result}")
            else:
                logger.info(f"Successful task result: {task_result}")

        return tasks_only

    async def update_and_monitor_trades(self, all_tasks, price_check_tasks):
        update_task = asyncio.create_task(self.watchlist.update(price_check_tasks))
        monitor_trades_task = asyncio.create_task(
            self.bot_controller.trade_manager.monitor_trades(self.watchlist)
        )

        return update_task, monitor_trades_task

    async def process_task_results(self, all_tasks, monitor_trades_task):
        done_tasks, pending_tasks = await asyncio.wait(
            all_tasks,
            return_when=asyncio.FIRST_EXCEPTION,
            timeout=60,  # Set a timeout for asyncio.wait
        )

        # for task in done_tasks:
        #     if task.exception() is not None:
        #         logger.error(f"Error in task {task} execution: {task.exception()}")
        #     else:
        #         logger.info(f"Task {task} completed successfully")

        if monitor_trades_task in done_tasks:
            if monitor_trades_task.exception() is not None:
                logger.error(
                    f"Error in monitor_trades task: {monitor_trades_task.exception()}"
                )
            else:
                logger.info("monitor_trades task completed successfully")

    async def get_whale_buy_tokens(self):
        whale_tokens = []
        timeframe = 24  # Let's say we want transactions from the last 24 hours

        for whale in self.whale_addresses:
            transactions = await self.bot_controller.blockchain_manager.get_transactions_by_address(
                whale, timeframe
            )

            # Filter out sales, we are only interested in buys
            buy_transactions = [
                tx
                for tx in transactions
                if tx["from"] == whale and tx["to"] == tx["token_contract"]
            ]

            for transaction in buy_transactions:
                token_data = get_token_data(transaction)
                token_data["date"] = transaction[
                    "timestamp"
                ]  # Assuming 'timestamp' is a datetime object
                whale_tokens.append(token_data)

        # Sort by date in descending order, i.e., most recent first
        whale_tokens_sorted = sorted(
            whale_tokens, key=lambda k: k["date"], reverse=True
        )

        return whale_tokens_sorted
