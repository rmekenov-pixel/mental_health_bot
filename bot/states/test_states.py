from aiogram.fsm.state import State, StatesGroup


class TestStates(StatesGroup):
    choosing_test = State()
    answering = State()


class CheckInStates(StatesGroup):
    mood = State()
    anxiety = State()
    energy = State()
    sleep_hours = State()
    sleep_quality = State()


class ReminderStates(StatesGroup):
    waiting_time = State()