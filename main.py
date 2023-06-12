import asyncio
import logging

from bot_controller import BotController
from managers.data_management import DataManagement
from managers.token_status_manager import TokenStatusManager
from models.chain_constants import SelectedChain
from token_info.token_watchlist import TokenWatchlist

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def get_select_chain_input(selected_chain_options):
    while True:
        print("Available chain options:")
        for i, option in enumerate(selected_chain_options, start=1):
            print(f"{i}. {option.value}")

        user_input = input("Enter the number corresponding to your selected chain: ")

        try:
            option_index = int(user_input) - 1
            if 0 <= option_index < len(selected_chain_options):
                selected_chain = selected_chain_options[option_index]
                return selected_chain
        except ValueError:
            pass

        print("Invalid input. Please try again.")


async def main(selected_chain):
    bot_controller: BotController = initialize_bot_controller(selected_chain)
    watchlist: TokenWatchlist = TokenWatchlist(
        bot_controller.MAX_TOKENS_MONITORED, bot_controller.blockchain_manager
    )
    await bot_controller.token_monitor.load_monitored_tokens()
    await bot_controller.token_analysis.load_token_score_cache()
    await watchlist.load_from_file()

    token_status_manager: TokenStatusManager = TokenStatusManager(
        bot_controller.token_analysis, bot_controller.token_monitor
    )

    while True:
        try:
            factory_contract = bot_controller.blockchain_manager.get_dex_contract()
            all_tasks = set()

            new_tokens = await get_new_tokens(bot_controller, factory_contract)

            logging.info(f"New tokens: {new_tokens}")

            (
                price_check_tasks,
                tokens_with_check_tasks,
            ) = await token_status_manager.create_token_check_tasks(new_tokens)

            logging.info(f"Price check tasks: {price_check_tasks}")
            logging.info(f"Tokens with check tasks: {tokens_with_check_tasks}")

            tasks_only = [task for task, _, _, _ in price_check_tasks]
            all_tasks.update(tasks_only)
            # Wait for all price check tasks to complete
            results = await asyncio.gather(*tasks_only, return_exceptions=True)

            for task_result in results:
                if isinstance(task_result, Exception):
                    logging.error(f"Error in price check task: {task_result}")
                else:
                    logging.info(f"Successful task result: {task_result}")

            all_tasks.add(asyncio.create_task(watchlist.update(price_check_tasks)))

            monitor_trades_task = asyncio.create_task(
                bot_controller.trade_manager.monitor_trades(watchlist)
            )
            all_tasks.add(monitor_trades_task)

            done_tasks, pending_tasks = await asyncio.wait(
                all_tasks, return_when=asyncio.FIRST_EXCEPTION
            )

            for task in done_tasks:
                if task.exception() is not None:
                    logging.error(f"Error in task {task} execution: {task.exception()}")
                else:
                    logging.info(f"Task {task} completed successfully")

            if monitor_trades_task in done_tasks:
                if monitor_trades_task.exception() is not None:
                    logging.error(
                        f"Error in monitor_trades task: {monitor_trades_task.exception()}"
                    )
                else:
                    logging.info("monitor_trades task completed successfully")

        except Exception as error:
            logging.exception(f"Error in main loop: {error}", exc_info=True)

        await asyncio.sleep(60)


def initialize_bot_controller(selected_chain):
    data_manager: DataManagement = DataManagement()
    return BotController(
        data_manager=data_manager,
        user_selected_chain=selected_chain,
        reset_userdata_on_load=False,
    )


async def get_new_tokens(bot_controller: BotController, factory_contract):
    # Set the ratio
    tvl_to_volume_ratio = 4  # Example ratio

    # Calculate Volume
    min_volume_usd = int(
        bot_controller.data_manager.config["min_liquidity_usd"] / tvl_to_volume_ratio
    )

    new_tokens = await bot_controller.protocol_manager.get_tokens(
        factory_contract,
        bot_controller.data_manager.config["max_created_threshold"],
        bot_controller.data_manager.config["min_liquidity_usd"],
        bot_controller.data_manager.config["max_liquidity_usd"],
        min_volume_usd,
    )
    # logging.info(f'###GETTING NEW TOKENS###: {new_tokens}')
    return new_tokens


user_selected_chain = get_select_chain_input(list(SelectedChain))
print(f"Selected chain: {user_selected_chain.value}")

if __name__ == "__main__":
    asyncio.run(main(user_selected_chain), debug=True)
