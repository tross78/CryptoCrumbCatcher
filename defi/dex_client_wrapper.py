import asyncio
from concurrent.futures import ThreadPoolExecutor


class DexClientWrapper:
    def __init__(self, dex_client):
        self.dex_client = dex_client
        self.executor = ThreadPoolExecutor(max_workers=5)

    async def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        loop = asyncio.get_running_loop()
        try:
            price = await loop.run_in_executor(
                self.executor,
                self.dex_client.get_price_input,
                token_in,
                token_out,
                token_trade_amount,
                fee,
            )
            return price
        except Exception as e:
            print(f"Could not get the input price: {str(e)}")
            return -1

    async def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        loop = asyncio.get_running_loop()
        try:
            price = await loop.run_in_executor(
                self.executor,
                self.dex_client.get_price_output,
                token_in,
                token_out,
                token_trade_amount,
                fee,
            )
            return price
        except Exception as e:
            print(f"Could not get the output price for token {token_in}: {str(e)}")
            return -1

    def make_trade(self, token_address, native_token_address, trade_amount):
        self.dex_client.make_trade(token_address, native_token_address, trade_amount)

    def make_trade_output(self, token_address, native_token_address, trade_amount):
        self.dex_client.make_trade_output(
            token_address, native_token_address, trade_amount
        )

    def approve(self, token_address, max_approval):
        self.dex_client.approve(token_address, max_approval)
