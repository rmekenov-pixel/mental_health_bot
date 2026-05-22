from aiogram.fsm.state import State, StatesGroup


class TestStates(StatesGroup):
    choosing_test = State()
    answering = State()


class CheckInStates(StatesGroup):
    mood = State()
    anxiety = State()
    energy = State()