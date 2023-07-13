import asyncio

from logger_config import logger
from workers import ChainWorker


class NewTokenWorker(ChainWorker):
    async def work_on_chain(self, stdscr):
        all_tasks = set()
        await self.watchlist.load_from_file()

        while True:
            current_bot_chain = (
                self.bot_controller.blockchain_manager.get_current_chain()
            )
            # .clear()
            stdscr.addstr(20, 0, f"Working on chain: {current_bot_chain.name}")
            stdscr.refresh()
            try:
                new_tokens = await self.get_new_tokens()
                logger.info(f"New tokens: {new_tokens}")

                (
                    tasks_only,
                    price_check_tasks_with_params,
                ) = await self.perform_token_checks(new_tokens)

                all_tasks.update(tasks_only)

                update_task, monitor_trades_task = await self.update_and_monitor_trades(
                    all_tasks, price_check_tasks_with_params
                )
                all_tasks.add(update_task)
                all_tasks.add(monitor_trades_task)

                await self.process_task_results(all_tasks, monitor_trades_task)
            except Exception as error:
                logger.exception(f"Error in main loop: {error}", exc_info=True)

            await asyncio.gather(*all_tasks)
            # stdscr.clear()
            # stdscr.addstr(20, 0, f"Finished working on chain: {current_bot_chain.name}")
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
                    text = text + " " + key + ": " + str(value)
                    stdscr.addstr(
                        y,
                        x,
                        text,
                    )
                    x = x + 25
                y = y + 1
                x = 0

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

    async def update_and_monitor_trades(self, all_tasks, price_check_tasks_with_params):
        update_task = asyncio.create_task(
            self.watchlist.update(price_check_tasks_with_params)
        )
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
            # else:
            #     logger.info("monitor_trades task completed successfully")

    async def get_new_tokens(self):
        # Set the ratio
        tvl_to_volume_ratio = 4  # Example ratio

        # Calculate Volume
        min_volume_usd = int(
            self.bot_controller.data_manager.config["min_liquidity_usd"]
            / tvl_to_volume_ratio
        )

        new_tokens = await self.bot_controller.protocol_manager.get_tokens(
            self.bot_controller.data_manager.config["max_created_threshold"],
            self.bot_controller.data_manager.config["min_liquidity_usd"],
            self.bot_controller.data_manager.config["max_liquidity_usd"],
            min_volume_usd,
        )
        # logger.info(f'###GETTING NEW TOKENS###: {new_tokens}')
        return new_tokens
