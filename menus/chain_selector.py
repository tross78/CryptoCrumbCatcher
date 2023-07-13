import curses
from typing import List

from models.chain_constants import SelectedChain


class ChainSelector:
    def __init__(self, stdscr, selected_chain_options):
        self.stdscr = stdscr
        self.selected_chain_options = selected_chain_options

    def get_select_chain_input(self):
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "Available chain options:")
        for i, option in enumerate(self.selected_chain_options, start=1):
            self.stdscr.addstr(i, 0, f"{i}. {option.value}")

        prompt = "Enter the number corresponding to your selected chain: "
        self.stdscr.addstr(i + 1, 0, prompt)

        # Adjust the cursor position
        curses.curs_set(1)  # Make the cursor visible
        self.stdscr.move(i + 1, len(prompt))
        self.stdscr.refresh()

        selected_chain = None
        while True:
            try:
                user_input = int(
                    self.stdscr.getstr().decode("utf-8")
                )  # get the input string and convert it to int
                index = user_input - 1
                if 0 <= index < len(self.selected_chain_options):
                    selected_chain = self.selected_chain_options[index]
                    break
            except ValueError:
                self.stdscr.addstr(i + 2, 0, f"Invalid option. Please try again.")
                self.stdscr.refresh()

        return selected_chain
