"""All InlineKeyboard builders."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton as Btn


def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


# ── Main menu ──────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="🔍 Парсер", callback_data="menu:parser"),
         Btn(text="💌 Рассыльщик", callback_data="menu:mailer")],
        [Btn(text="👥 Инвайтер", callback_data="menu:inviter"),
         Btn(text="📊 Результаты", callback_data="menu:results")],
        [Btn(text="⚡ Аккаунты", callback_data="menu:accounts"),
         Btn(text="🤖 Бот-рассылка", callback_data="menu:broadcast")],
        [Btn(text="❓ Помощь", callback_data="menu:help")],
    )


def back(target="main") -> InlineKeyboardMarkup:
    return _kb([Btn(text="◀️ Назад", callback_data=f"menu:{target}")])


# ── Parser ─────────────────────────────────────────────────────────────────────

def parser_menu() -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="🔑 По ключевым словам", callback_data="parser:keywords")],
        [Btn(text="👥 Участники группы", callback_data="parser:members")],
        [Btn(text="👑 Только администраторы", callback_data="parser:admins")],
        [Btn(text="◀️ Назад", callback_data="menu:main")],
    )


def cancel_parse() -> InlineKeyboardMarkup:
    return _kb([Btn(text="⛔ Остановить", callback_data="parser:stop")])


def save_or_skip() -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="💾 Сохранить результат", callback_data="parser:save"),
         Btn(text="🗑 Отмена", callback_data="menu:main")],
    )


# ── Results ────────────────────────────────────────────────────────────────────

def results_list(results: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for r in results[:20]:
        mode_icon = {"keyword": "🔑", "members": "👥", "admins": "👑"}.get(r["mode"], "📋")
        label = f"{mode_icon} {r['name']} — {r['total']}"
        rows.append([Btn(text=label, callback_data=f"result:view:{r['id']}")])
    rows.append([Btn(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def result_detail(rid: int) -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="📥 Экспорт CSV", callback_data=f"result:csv:{rid}"),
         Btn(text="👥 Инвайтер", callback_data=f"result:invite:{rid}")],
        [Btn(text="💌 DM-рассылка", callback_data=f"result:dm:{rid}")],
        [Btn(text="🗑 Удалить", callback_data=f"result:delete:{rid}"),
         Btn(text="◀️ Назад", callback_data="menu:results")],
    )


def confirm_delete(rid: int) -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="✅ Да, удалить", callback_data=f"result:delete_confirm:{rid}"),
         Btn(text="❌ Отмена", callback_data=f"result:view:{rid}")],
    )


# ── Accounts ───────────────────────────────────────────────────────────────────

def accounts_list(accounts: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for a in accounts:
        icon = "✅" if a["status"] == "active" else "❌"
        name = a["first_name"] or a["username"] or f"ID{a['id']}"
        rows.append([Btn(text=f"{icon} {name} (@{a['username'] or '?'})",
                         callback_data=f"acc:view:{a['id']}")])
    rows.append([Btn(text="🔄 Обновить список", callback_data="acc:refresh")])
    rows.append([Btn(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_detail(acc_id: int, status: str) -> InlineKeyboardMarkup:
    toggle_label = "🔴 Деактивировать" if status == "active" else "🟢 Активировать"
    toggle_cb = f"acc:deactivate:{acc_id}" if status == "active" else f"acc:activate:{acc_id}"
    return _kb(
        [Btn(text=toggle_label, callback_data=toggle_cb)],
        [Btn(text="🗑 Удалить из списка", callback_data=f"acc:delete:{acc_id}")],
        [Btn(text="◀️ Назад", callback_data="menu:accounts")],
    )


def account_select(accounts: list[dict], selected: list[int]) -> InlineKeyboardMarkup:
    rows = []
    for a in accounts:
        check = "✅" if a["id"] in selected else "☐"
        name = a["first_name"] or a["username"] or f"ID{a['id']}"
        rows.append([Btn(text=f"{check} {name} (@{a['username'] or '?'})",
                         callback_data=f"acc:toggle:{a['id']}")])
    rows.append([Btn(text="✔️ Готово", callback_data="acc:done"),
                 Btn(text="✖️ Отмена", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Inviter / Mailer ───────────────────────────────────────────────────────────

def cancel_job() -> InlineKeyboardMarkup:
    return _kb([Btn(text="⛔ Остановить", callback_data="job:stop")])


def mailer_menu(bot_subs_count: int) -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text=f"🤖 Бот-рассылка ({bot_subs_count} подписчиков)", callback_data="mailer:bot")],
        [Btn(text="👤 DM через аккаунты", callback_data="mailer:accounts")],
        [Btn(text="◀️ Назад", callback_data="menu:main")],
    )


def skip_media() -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text="➡️ Без медиа", callback_data="media:skip"),
         Btn(text="✖️ Отмена", callback_data="menu:main")],
    )


def confirm_send(label="Отправить") -> InlineKeyboardMarkup:
    return _kb(
        [Btn(text=f"✅ {label}", callback_data="send:confirm"),
         Btn(text="❌ Отмена", callback_data="menu:main")],
    )
