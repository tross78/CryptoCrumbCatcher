from dataclasses import dataclass

@dataclass
class DexTradeChainData:
    name: str
    display_name: str
    rpc_url: str
    uniswap_graph_url: str
    factory_address: str
    native_token_address: str
    # Additional chain-specific properties if needed