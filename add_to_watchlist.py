import asyncio
import signal
from itertools import cycle

from bot_controller import BotController
from managers.async_task_manager import AsyncTaskManager
from managers.data_management import DataManagement
from menus.chain_selector import ChainSelector
from models.chain_constants import SelectedChain
from token_info.token_watchlist import TokenWatchlist


async def main():
    chain_selector = ChainSelector(list(SelectedChain))
    user_selected_chains = cycle(chain_selector.get_select_chain_input())

    selected_chain = next(user_selected_chains)

    loop = asyncio.get_event_loop()
    task_manager = AsyncTaskManager(loop)
    loop.add_signal_handler(signal.SIGINT, task_manager.cancel_all_tasks)

    bot_controller: BotController = initialize_bot_controller(selected_chain)
    await bot_controller.token_monitor.load_monitored_tokens()

    watchlist = TokenWatchlist(9, bot_controller.blockchain_manager)

    pool_instance = None

    while not pool_instance:
        print("Enter token address:")
        user_token_address = input()

        print("Enter pool fee:")
        user_pool_fee = int(input())

        token_address = (
            bot_controller.blockchain_manager.web3_instance.to_checksum_address(
                user_token_address
            )
        )

        pool_instance = bot_controller.protocol_manager.get_pool_instance(
            bot_controller.blockchain_manager.current_native_token_address,
            token_address,
            user_pool_fee,
        )

        if not pool_instance:
            pool_instance = bot_controller.protocol_manager.get_pool_instance(
                token_address,
                bot_controller.blockchain_manager.current_native_token_address,
                user_pool_fee,
            )

        if pool_instance:
            break
        else:
            print("No pool found! Try again.")

    pool_address = pool_instance.address

    token_trade_amount = int(
        bot_controller.wallet_manager.get_native_token_balance_percentage(
            bot_controller.data_manager.config["trade_amount_percentage"]
        )
    )

    token_base_value = await bot_controller.protocol_manager.get_min_token_for_native(
        token_address, token_trade_amount, user_pool_fee
    )
    await watchlist.load_from_file()
    await watchlist.add(token_address, user_pool_fee, pool_address, token_base_value)


def initialize_bot_controller(selected_chain):
    data_manager: DataManagement = DataManagement()
    return BotController(
        data_manager=data_manager,
        user_selected_chain=selected_chain,
        reset_userdata_on_load=False,
    )


if __name__ == "__main__":
    asyncio.run(main())
