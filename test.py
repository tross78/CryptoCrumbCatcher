# Online Python compiler (interpreter) to run Python online.
# Write Python 3 code in this online editor and run it.
from decimal import Decimal

from managers.blockchain_manager import BlockchainManager
from managers.data_management import DataManagement
from models.chain_constants import SelectedChain
from test_class import TestClass

# Values are given
fee = 3000  # in parts per million
initial_investment = 60000000000000000  # in Wei

profit_margin = 0.01  # 1% desired profit margin


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

blockchain_manager = BlockchainManager(user_selected_chain)
data_manager = DataManagement()

test_class = TestClass(data_manager, blockchain_manager)

print(test_class.calculate_roi_multiplier(3000))
