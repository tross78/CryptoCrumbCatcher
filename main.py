import asyncio
import signal
from itertools import cycle

from bot_controller import BotController
from logger_config import logger
from managers.data_management import DataManagement
from managers.token_status_manager import TokenStatusManager
from models.chain_constants import SelectedChain
from token_info.token_watchlist import TokenWatchlist


def get_select_chain_input(selected_chain_options):
    selected_chains = selected_chain_options
    while True:
        print("\nAvailable chain options:")
        for i, option in enumerate(selected_chain_options, start=1):
            print(f"{i}. {option.value}")

        print(
            "Enter the numbers corresponding to your selected chains, separated by commas, or press 'q' to finish: "
        )
        user_input = input()

        if user_input.lower() == "q":
            break
        selected_chains = []
        try:
            indices = [int(i) - 1 for i in user_input.split(",")]
            for index in indices:
                if 0 <= index < len(selected_chain_options):
                    selected_chain = selected_chain_options[index]
                    selected_chains.append(selected_chain)
                else:
                    print(f"Invalid option: {index+1}. Please try again.")
        except ValueError:
            print("Invalid input. Please try again.")

    return selected_chains


def cancel_all_tasks(loop):
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.gather(*to_cancel, loop=loop, return_exceptions=True)
    )

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during asyncio.run() shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )


async def work_on_chain(selected_chains, bot_controller: BotController):
    watchlist: TokenWatchlist = TokenWatchlist(
        bot_controller.MAX_TOKENS_MONITORED, bot_controller.blockchain_manager
    )
    all_tasks = set()
    await watchlist.load_from_file()
    while True:
        token_status_manager: TokenStatusManager = TokenStatusManager(
            bot_controller.token_analysis, bot_controller.token_monitor
        )
        current_bot_chain = bot_controller.blockchain_manager.get_current_chain()
        print(f"Working on chain: {current_bot_chain.name}")
        try:
            new_tokens = await get_new_tokens(bot_controller)

            logger.info(f"New tokens: {new_tokens}")

            (
                price_check_tasks,
                tokens_with_check_tasks,
            ) = await token_status_manager.create_token_check_tasks(new_tokens)

            logger.info(f"Price check tasks: {price_check_tasks}")
            logger.info(f"Tokens with check tasks: {tokens_with_check_tasks}")

            tasks_only = [task for task, _, _, _ in price_check_tasks]
            all_tasks.update(tasks_only)
            # Wait for all price check tasks to complete
            results = await asyncio.gather(*tasks_only, return_exceptions=True)

            for task_result in results:
                if isinstance(task_result, Exception):
                    logger.error(f"Error in price check task: {task_result}")
                else:
                    logger.info(f"Successful task result: {task_result}")

            all_tasks.add(asyncio.create_task(watchlist.update(price_check_tasks)))

            monitor_trades_task = asyncio.create_task(
                bot_controller.trade_manager.monitor_trades(watchlist)
            )
            all_tasks.add(monitor_trades_task)

            done_tasks, pending_tasks = await asyncio.wait(
                all_tasks,
                return_when=asyncio.FIRST_EXCEPTION,
                timeout=60,  # Set a timeout for asyncio.wait
            )

            for task in done_tasks:
                if task.exception() is not None:
                    logger.error(f"Error in task {task} execution: {task.exception()}")
                else:
                    logger.info(f"Task {task} completed successfully")

            if monitor_trades_task in done_tasks:
                if monitor_trades_task.exception() is not None:
                    logger.error(
                        f"Error in monitor_trades task: {monitor_trades_task.exception()}"
                    )
                else:
                    logger.info("monitor_trades task completed successfully")
        except Exception as error:
            logger.exception(f"Error in main loop: {error}", exc_info=True)

        # sleep_task = asyncio.create_task(asyncio.sleep(60))
        # all_tasks.add(sleep_task)
        # check if all tasks are done
        # all_tasks = asyncio.all_tasks()
        if all(
            task.done() for task in all_tasks
        ):  # all_tasks should be your set of tasks, not the result of asyncio.all_tasks()
            print(f"Finished working on chain: {current_bot_chain.name}")
            selected_chain = next(selected_chains)
            bot_controller.blockchain_manager.set_current_chain(selected_chain)
            bot_controller.blockchain_manager.set_provider()


async def main(selected_chains):
    selected_chain = next(selected_chains)
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, cancel_all_tasks, loop)
    bot_controller: BotController = initialize_bot_controller(selected_chain)
    await bot_controller.token_monitor.load_monitored_tokens()
    # await bot_controller.token_analysis.load_token_score_cache()
    await work_on_chain(selected_chains, bot_controller)


def initialize_bot_controller(selected_chain):
    data_manager: DataManagement = DataManagement()
    return BotController(
        data_manager=data_manager,
        user_selected_chain=selected_chain,
        reset_userdata_on_load=False,
    )


async def get_new_tokens(bot_controller: BotController):
    # Set the ratio
    tvl_to_volume_ratio = 4  # Example ratio

    # Calculate Volume
    min_volume_usd = int(
        bot_controller.data_manager.config["min_liquidity_usd"] / tvl_to_volume_ratio
    )

    new_tokens = await bot_controller.protocol_manager.get_tokens(
        bot_controller.data_manager.config["max_created_threshold"],
        bot_controller.data_manager.config["min_liquidity_usd"],
        bot_controller.data_manager.config["max_liquidity_usd"],
        min_volume_usd,
    )
    # logger.info(f'###GETTING NEW TOKENS###: {new_tokens}')
    return new_tokens


user_selected_chains = get_select_chain_input(list(SelectedChain))
# print(f"Selected chain: {user_selected_chain.value}")

if __name__ == "__main__":
    asyncio.run(main(cycle(user_selected_chains)))
