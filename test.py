# Online Python compiler (interpreter) to run Python online.
# Write Python 3 code in this online editor and run it.
from bot_controller import BotController
from managers.data_management import DataManagement
from models.chain_constants import SelectedChain


def initialize_bot_controller(selected_chain):
    data_manager: DataManagement = DataManagement()
    bot = BotController(
        data_manager=data_manager,
        user_selected_chain=selected_chain,
        reset_userdata_on_load=False,
    )

    # bot.protocol_manager.approve(
    #     "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
    #     10000000000000000,  # 0.01 ETH
    # )

    bot.protocol_manager.make_trade_output(
        "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # test_class.blockchain_manager.current_native_token_address,  # GETH
        10000000000000000,  # 0.01 ETH
    )


def get_select_chain_input(selected_chain_options):
    while True:
        print("Available chain options:")
        for i, option in enumerate(selected_chain_options, start=1):
            print(f"{i}. {option.value}")

        user_input = input("Enter the number corresponding to your selected chain: ")

        try:
            option_index = int(user_input) - 1
            if 0 <= option_index < len(selected_chain_options):
                selected_chain = selected_chain_options[option_index]
                return selected_chain
        except ValueError:
            pass

        print("Invalid input. Please try again.")


user_selected_chain = get_select_chain_input(list(SelectedChain))
print(f"Selected chain: {user_selected_chain.value}")

initialize_bot_controller(user_selected_chain)
