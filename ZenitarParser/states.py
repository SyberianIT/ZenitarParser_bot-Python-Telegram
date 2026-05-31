from aiogram.fsm.state import State, StatesGroup


class ParserSG(StatesGroup):
    keywords = State()
    group_link = State()
    result_name = State()


class InviterSG(StatesGroup):
    target = State()
    accounts = State()
    delay = State()
    confirm = State()


class MailerSG(StatesGroup):
    result = State()       # account DM: pick result
    message = State()
    media = State()        # optional media upload
    accounts = State()     # account DM: pick accounts
    delay = State()
    confirm = State()


class BotBroadcastSG(StatesGroup):
    message = State()
    media = State()
    confirm = State()
