import asyncio
import curses
import signal
from itertools import cycle

from bot_controller import BotController
from managers.async_task_manager import AsyncTaskManager
from managers.data_management import DataManagement
from menus.chain_selector import ChainSelector
from menus.worker_selector import WorkerSelector
from models.chain_constants import SelectedChain


def initialize_bot_controller(selected_chain, stdscr):
    data_manager: DataManagement = DataManagement()
    return BotController(
        data_manager=data_manager,
        user_selected_chain=selected_chain,
        reset_userdata_on_load=False,
    )


async def main(stdscr, selected_chains):
    # Get the terminal size
    terminal_height, terminal_width = stdscr.getmaxyx()

    # Define your window size
    width = terminal_width
    height = terminal_height  # Full terminal height

    # Create the window
    win = curses.newwin(height, width, 0, 0)

    user_selected_chains = cycle([selected_chains])
    selected_chain = next(user_selected_chains)
    loop = asyncio.get_event_loop()
    task_manager = AsyncTaskManager(loop)
    loop.add_signal_handler(signal.SIGINT, task_manager.cancel_all_tasks)

    bot_controller: BotController = initialize_bot_controller(selected_chain, win)
    await bot_controller.token_monitor.load_monitored_tokens()

    worker_selector = WorkerSelector(bot_controller, user_selected_chains, win)

    worker = worker_selector.get_selected_worker()

    await worker.work_on_chain(win)


def start(stdscr):
    curses.echo()
    chain_selector = ChainSelector(stdscr, list(SelectedChain))
    selected_chains = chain_selector.get_select_chain_input()
    asyncio.run(main(stdscr, selected_chains))


if __name__ == "__main__":
    curses.wrapper(start)
