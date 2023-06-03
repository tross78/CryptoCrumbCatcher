class PriceProvider:
    def __init__(self, dex_client):
        self.dex_client = dex_client

    def get_price_input(self, token_in, token_out, token_trade_amount, fee):
        try:
            return self.dex_client.get_price_input(
                token_in, token_out, token_trade_amount, fee
            )
        except Exception as e:
            print(f"Could not get the input price: {str(e)}")
            return -1

    def get_price_output(self, token_in, token_out, token_trade_amount, fee):
        try:
            price = self.dex_client.get_price_output(
                token_in, token_out, token_trade_amount, fee
            )
            return price
        except Exception as e:
            print(f"Could not get the output price for token {token_in}: {str(e)}")
            return -1
