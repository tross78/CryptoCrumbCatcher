import logging
from decimal import Decimal

from defi.protocol_manager import ProtocolManager
from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from utils import calculate_estimated_net_token_amount_wei_after_fees


class TestClass:
    def __init__(
        self,
        data_manager: DataManagement,
        blockchain_manager: BlockchainManager,
        protocol_manager: ProtocolManager,
    ):
        self.blockchain_manager = blockchain_manager
        self.data_manager = data_manager
        self.protocol_manager = protocol_manager
        self.profit_margin = Decimal("0.01")
