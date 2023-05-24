class TokenPriceProvider:
    def __init__(self, uniswap_client, mock_data_provider=None):
        self.uniswap_client = uniswap_client
        self.mock_data_provider = mock_data_provider

    def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        if self.mock_data_provider:
            return self.mock_data_provider.get_price_input(token_in, token_out, token_trade_amount, fee)
        else:
            return self.uniswap_client.get_price_input(token_in, token_out, token_trade_amount, fee)

    def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        if self.mock_data_provider:
            return self.mock_data_provider.get_price_output(token_in, token_out, token_trade_amount, fee)
        else:
            return self.uniswap_client.get_price_output(token_in, token_out, token_trade_amount, fee)