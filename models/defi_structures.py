class Token:
    def __init__(self, id: str, symbol: str, name: str):
        self.id = id.lower()
        self.symbol = symbol
        self.name = name

    def to_json(self):
        return {"id": self.id, "name": self.name, "symbol": self.symbol}


class Pool:
    def __init__(
        self, id: str, token0: Token, token1: Token, fee: int, volumeUSD: float
    ):
        self.id = id.lower()
        self.token0 = token0
        self.token1 = token1
        self.fee = fee
        self.volumeUSD = volumeUSD

    def to_json(self):
        return {"id": self.id}


class Fee:
    def __init__(self, id: str, basis_points: str):
        self.id = id
        self.basis_points = basis_points

    def to_json(self):
        return {"id": self.id, "basis_points": self.basis_points}
