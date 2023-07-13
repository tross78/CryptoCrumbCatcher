import asyncio
from concurrent.futures import ThreadPoolExecutor

from retrying import retry

from logger_config import logger


class DexClientWrapper:
    def __init__(self, client):
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=5)

    # Decorator that will make the function retry on exceptions
    def retry_if_exception(self, exception):
        """Return True if we should retry (in this case when it's an Exception), False otherwise"""
        return isinstance(exception, Exception)

    @retry(
        retry_on_exception=retry_if_exception,
        stop_max_attempt_number=3,
        wait_exponential_multiplier=1000,
        wait_exponential_max=10000,
    )
    async def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        loop = asyncio.get_running_loop()
        try:
            price = await loop.run_in_executor(
                self.executor,
                self.client.get_price_input,
                token_in,
                token_out,
                token_trade_amount,
                fee,
            )
            return price
        except Exception as e:
            logger.error(f"Could not get the input price: {str(e)}")
            raise  # To trigger retry we need to re-raise the exception

    @retry(
        retry_on_exception=retry_if_exception,
        stop_max_attempt_number=3,
        wait_exponential_multiplier=1000,
        wait_exponential_max=10000,
    )
    async def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        loop = asyncio.get_running_loop()

        try:
            price = await loop.run_in_executor(
                self.executor,
                self.client.get_price_output,
                token_in,
                token_out,
                token_trade_amount,
                fee,
            )
            return price
        except Exception as e:
            logger.error(
                f"Could not get the output price for token {token_in}: {str(e)}"
            )
            raise  # To trigger retry we need to re-raise the exception

    def make_trade(self, token_address, native_token_address, trade_amount, fee):
        self.client.make_trade(
            token_address,
            native_token_address,
            trade_amount,
            None,
            fee,
        )

    def make_trade_output(self, token_address, native_token_address, trade_amount):
        self.client.make_trade_output(token_address, native_token_address, trade_amount)

    def get_pool_instance(self, token_0, token_1, fee):
        pool_instance = self.client.get_pool_instance(token_0, token_1, fee)
        return pool_instance
