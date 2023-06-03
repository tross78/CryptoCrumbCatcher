from dataclasses import dataclass


@dataclass
class DexTradeChainData:
    name: str
    display_name: str
    short_name: str
    rpc_url: str
    graph_url: str
    graph_type: str
    factory_address: str
    native_token_address: str
    # Additional chain-specific properties if needed
