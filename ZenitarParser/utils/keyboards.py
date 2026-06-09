from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Парсер", callback_data="parser_menu")
    kb.button(text="🎯 Аудитория", callback_data="audience_menu")
    kb.button(text="📨 Инвайтер", callback_data="inviter_menu")
    kb.button(text="📢 Рассыльщик", callback_data="sender_menu")
    kb.button(text="⏰ Планировщик", callback_data="scheduler_menu")
    kb.button(text="🚫 Чёрный список", callback_data="blacklist_menu")
    kb.button(text="👥 Аккаунты", callback_data="accounts_menu")
    kb.button(text="🤖 Боты", callback_data="bots_menu")
    kb.button(text="📊 Статистика", callback_data="stats_menu")
    kb.button(text="⚙️ Настройки", callback_data="settings_menu")
    kb.button(text="🔄 Обновить", callback_data="refresh")
    kb.adjust(2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def audience_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧹 Дедупликация", callback_data="aud_dedupe")
    kb.button(text="➕ Объединить", callback_data="aud_merge")
    kb.button(text="➖ Вычесть (исключить)", callback_data="aud_subtract")
    kb.button(text="🔬 Фильтр", callback_data="aud_filter")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def audience_filter_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Только с @username", callback_data="af_only_username")
    kb.button(text="💎 Только Premium", callback_data="af_only_premium")
    kb.button(text="🚫 Без ботов", callback_data="af_no_bots")
    kb.button(text="🧑 Только люди", callback_data="af_only_humans")
    kb.button(text="◀️ Назад", callback_data="audience_menu")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def done_kb(done_cb: str, back: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data=done_cb)
    kb.button(text="◀️ Назад", callback_data=back)
    kb.adjust(2)
    return kb.as_markup()


def parser_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Участники группы", callback_data="parse_members")
    kb.button(text="✍️ Активные юзеры", callback_data="parse_active")
    kb.button(text="🔎 По ключевым словам", callback_data="parse_keyword")
    kb.button(text="❤️ По реакциям на пост", callback_data="parse_reactions")
    kb.button(text="💬 Комментаторы поста", callback_data="parse_comments")
    kb.button(text="📂 Мои экспорты", callback_data="parse_exports")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 2, 1, 1, 1)
    return kb.as_markup()


def member_filter_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Все участники", callback_data="mf_all")
    kb.button(text="🕐 Недавно активные", callback_data="mf_recent")
    kb.button(text="⭐ Администраторы", callback_data="mf_admins")
    kb.button(text="🤖 Только боты", callback_data="mf_bots")
    kb.button(text="◀️ Назад", callback_data="parser_menu")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def inviter_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Загрузить CSV", callback_data="invite_load")
    kb.button(text="📋 Из последнего парса", callback_data="invite_last")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(2, 1)
    return kb.as_markup()


def sender_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Через юзербот (Pyrogram)", callback_data="send_userbot")
    kb.button(text="🤖 Через бота (Bot API)", callback_data="send_bot")
    kb.button(text="◀️ Назад", callback_data="main_menu")
    kb.adjust(1, 1, 1)
    return kb.as_markup()


def stop_kb(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛑 Остановить", callback_data=f"stop_{task_id}")
    return kb.as_markup()


def back_kb(target: str = "main_menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data=target)
    return kb.as_markup()


def confirm_kb(yes_cb: str, no_cb: str = "main_menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=yes_cb)
    kb.button(text="❌ Отмена", callback_data=no_cb)
    kb.adjust(2)
    return kb.as_markup()
