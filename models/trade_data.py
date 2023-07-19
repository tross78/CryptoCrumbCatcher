from dataclasses import dataclass
from enum import Enum


class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class TradeData:
    trade_type: TradeType
    input_amount: int
    expected_amount: int
    original_investment_eth: int


@dataclass
class PotentialTrade:
    token_address: str
    token_name: str
    pool_address: str
    fee: int
    token_base_value: int
