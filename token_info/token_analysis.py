import asyncio
from decimal import Decimal

from web3 import Web3

from defi.protocol_manager import ProtocolManager
from logger_config import logger
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from managers.tokensniffer_scaper import TokensnifferScraper
from managers.wallet_manager import WalletManager


class TokenAnalysis:
    def __init__(
        self,
        data_manager,
        blockchain_manager,
        protocol_manager,
        wallet_manager: WalletManager,
    ):
        self.data_manager: DataManagement = data_manager
        self.blockchain_manager: BlockchainManager = blockchain_manager
        self.protocol_manager: ProtocolManager = protocol_manager
        self.token_score_cache = {}
        self.wallet_manager = wallet_manager
        self.tokensniffer_scraper = TokensnifferScraper(
            data_manager, blockchain_manager
        )

    async def is_token_price_increase(self, token, fee, pool):
        trade_amount = int(
            self.wallet_manager.get_native_token_balance_percentage(
                self.data_manager.config["trade_amount_percentage"]
            )
        )
        try:
            logger.info("starting is_token_price_increase start_amount")
            start_amount = await self.protocol_manager.get_min_token_for_native(
                token.id,
                trade_amount,
                fee.basis_points,
            )

            start_pool_data = await self.protocol_manager.get_pool_data(pool.id)
            if start_pool_data:
                start_volume_usd = start_pool_data.volumeUSD
            else:
                start_volume_usd = -1

            await asyncio.sleep(self.data_manager.config["monitor_timeframe"] * 60)

            logger.info("starting is_token_price_increase end_amount")
            end_amount = await self.protocol_manager.get_min_token_for_native(
                token.id,
                trade_amount,
                fee.basis_points,
            )

            end_pool_data = await self.protocol_manager.get_pool_data(pool.id)
            if end_pool_data:
                end_volume_usd = end_pool_data.volumeUSD
            else:
                end_volume_usd = -1

            if (
                start_amount == -1
                or end_amount == -1
                or start_volume_usd == -1
                or end_volume_usd == -1
            ):
                return False, 0

            price_increase_threshold = self.data_manager.config[
                "price_increase_threshold"
            ]

            price_threshold_amount = int(
                Decimal(str(start_amount)) / Decimal(str(price_increase_threshold))
            )

            volume_increase_threshold = self.data_manager.config[
                "volume_increase_threshold"
            ]

            volume_threshold_amount = int(
                Decimal(str(start_volume_usd)) * Decimal(str(volume_increase_threshold))
            )

            logger.info(
                f"Token start amount: {start_amount} \
                Token end amount: {end_amount} \
                    Tokem Price Threshold amount: {price_threshold_amount}"
            )

            if (
                end_amount < price_threshold_amount
                and end_volume_usd > volume_threshold_amount
            ):
                return True, start_amount

            return False, start_amount

        except Exception as e:
            logger.error(f"Error in is_token_price_increase: {e}")
            return False, 0

    async def has_exploits(self, token_address):
        current_chain_name = self.blockchain_manager.get_current_chain().name
        if current_chain_name != "goerli_testnet":
            token_score = await self.tokensniffer_scraper.check_token_score(
                Web3.to_checksum_address(token_address)
            )
            logger.info(
                f"Token {token_address} exploit check: tokensniffer score {token_score}"
            )
            if token_score >= self.data_manager.config["token_rating_threshold"]:
                return False
            else:
                return True
        return False
