import asyncio

from logger_config import logger
from workers import ChainWorker


class WatchlistWorker(ChainWorker):
    async def work_on_chain(self, stdscr):
        all_tasks = set()
        await self.watchlist.load_from_file()
        stdscr.clear()
        current_bot_chain = self.bot_controller.blockchain_manager.get_current_chain()
        stdscr.addstr(20, 0, f"Working on chain: {current_bot_chain.name}")
        stdscr.refresh()
        while True:
            try:
                monitor_trades_task = await self.update_and_monitor_trades()
                all_tasks.add(monitor_trades_task)

                await self.process_task_results(all_tasks, monitor_trades_task)
            except Exception as error:
                logger.exception(f"Error in main loop: {error}", exc_info=True)

            await asyncio.gather(*all_tasks)
            monitored_tokens = self.bot_controller.token_monitor.get_monitored_tokens()

            x = 20
            y = 0
            for _, token_data in monitored_tokens.items():
                display_dict = {
                    "current_roi": token_data["current_roi"],
                    "expected_roi": token_data["expected_roi"],
                }
                text = token_data["token_address"]
                for key, value in display_dict.items():
                    text = text + " " + key + ": " + "{:.2f}".format(value)
                    stdscr.addstr(
                        y,
                        x,
                        text,
                    )
                    x = x + 25
                y = y + 1
                x = 20

            # stdscr.refresh()

            # stdscr.clear()
            # .addstr(0, 0, f"Finished working on chain: {current_bot_chain.name}")
            stdscr.refresh()
            selected_chain = next(self.selected_chains)
            self.bot_controller.blockchain_manager.set_current_chain(selected_chain)
            self.bot_controller.blockchain_manager.set_provider()

    async def perform_token_checks(self, new_tokens):
        (
            price_check_tasks_with_params,
            tokens_with_check_tasks,
        ) = await self.token_status_manager.create_token_check_tasks(new_tokens)

        logger.info(f"Price check tasks: {price_check_tasks_with_params}")
        logger.info(f"Tokens with check tasks: {tokens_with_check_tasks}")

        tasks_only = [task for task, _, _, _ in price_check_tasks_with_params]

        # Wait for all price check tasks to complete
        results = await asyncio.gather(*tasks_only, return_exceptions=True)

        for task_result in results:
            if isinstance(task_result, Exception):
                logger.error(f"Error in price check task: {task_result}")
            else:
                logger.info(f"Successful task result: {task_result}")

        # Now tasks_with_params contains the tasks together with their parameters
        return tasks_only, price_check_tasks_with_params

    async def update_and_monitor_trades(self):
        monitor_trades_task = asyncio.create_task(
            self.bot_controller.trade_manager.monitor_trades(self.watchlist)
        )

        return monitor_trades_task

    async def process_task_results(self, all_tasks, monitor_trades_task):
        done_tasks, pending_tasks = await asyncio.wait(
            all_tasks,
            return_when=asyncio.FIRST_EXCEPTION,
            timeout=60,  # Set a timeout for asyncio.wait
        )

        if monitor_trades_task in done_tasks:
            if monitor_trades_task.exception() is not None:
                logger.error(
                    f"Error in monitor_trades task: {monitor_trades_task.exception()}"
                )
