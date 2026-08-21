from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    waiting_game_id = State()


class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_amount = State()
    waiting_price = State()
