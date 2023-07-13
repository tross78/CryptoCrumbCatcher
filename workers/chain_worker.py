from typing import List

from bot_controller import BotController
from managers.token_status_manager import TokenStatusManager
from models.chain_constants import SelectedChain
from token_info.token_watchlist import TokenWatchlist


class ChainWorker:
    def __init__(
        self, bot_controller: BotController, selected_chains: List[SelectedChain]
    ):
        self.bot_controller = bot_controller
        self.token_status_manager: TokenStatusManager = TokenStatusManager(
            bot_controller.token_analysis, bot_controller.token_monitor
        )
        self.watchlist: TokenWatchlist = TokenWatchlist(
            bot_controller.MAX_TOKENS_MONITORED, bot_controller.blockchain_manager
        )
        self.selected_chains = selected_chains

    async def work_on_chain(self, stdscr):
        pass
