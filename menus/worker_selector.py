import curses

from bot_controller import BotController
from models.chain_constants import SelectedChain
from workers.chain_worker import ChainWorker
from workers.newtoken_worker import NewTokenWorker
from workers.watchlist_worker import WatchlistWorker


class WorkerSelector:
    def __init__(
        self,
        bot_controller: BotController,
        user_selected_chains: list[SelectedChain],
        stdscr,
    ):
        self.bot_controller = bot_controller
        self.user_selected_chains = user_selected_chains
        self.stdscr = stdscr
        self.selected_worker_options = {
            "Volatility Auto trading new tokens": 1,
            "Volatility Auto trading watchlist tokens only": 2,
        }

    def get_selected_worker(self) -> ChainWorker:
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "Available worker options:")
        for i, option in enumerate(self.selected_worker_options, start=1):
            self.stdscr.addstr(i, 0, f"{i}. {option}")

        prompt = "Select a worker to continue: "
        self.stdscr.addstr(i + 1, 0, prompt)

        # Adjust the cursor position
        curses.curs_set(1)  # Make the cursor visible
        self.stdscr.move(i + 1, len(prompt))
        self.stdscr.refresh()

        user_input = None
        while True:
            try:
                user_input = int(
                    self.stdscr.getstr().decode("utf-8")
                )  # get the input string and convert it to int
                if 1 <= user_input <= 2:
                    break
            except ValueError:
                self.stdscr.addstr(i + 2, 0, "Invalid option. Please try again.")
                self.stdscr.refresh()

        if user_input == 1:
            return NewTokenWorker(self.bot_controller, self.user_selected_chains)
        if user_input == 2:
            return WatchlistWorker(self.bot_controller, self.user_selected_chains)
