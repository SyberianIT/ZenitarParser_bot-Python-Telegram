import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import kb
import engine
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()


def _admin(uid): return uid == ADMIN_ID


@router.callback_query(F.data == "menu:accounts")
async def cb_accounts(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    accounts = await db.get_accounts()
    active = sum(1 for a in accounts if a["status"] == "active")
    await callback.message.edit_text(
        f"<b>⚡ Аккаунты</b>\n\n"
        f"Всего: {len(accounts)} | Активных: {active}\n\n"
        f"<i>Помести .session файлы в папку <code>sessions/</code> и нажми 🔄 Обновить</i>",
        reply_markup=kb.accounts_list(accounts),
    )


@router.callback_query(F.data == "acc:refresh")
async def cb_refresh(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer("🔄 Сканирую сессии…")
    sessions = engine.scan_sessions()

    added = checked = 0
    for s in sessions:
        info = await engine.check_account(s)
        if info:
            await db.upsert_account(
                s, info["first_name"], info["username"],
                info["tg_id"], info["phone"], info["dc_id"],
            )
            added += 1
        checked += 1

    accounts = await db.get_accounts()
    active = sum(1 for a in accounts if a["status"] == "active")
    await callback.message.edit_text(
        f"<b>⚡ Аккаунты</b>\n\n"
        f"Проверено: {checked} | Добавлено/обновлено: {added}\n"
        f"Всего в БД: {len(accounts)} | Активных: {active}",
        reply_markup=kb.accounts_list(accounts),
    )


@router.callback_query(F.data.startswith("acc:view:"))
async def cb_acc_view(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    acc_id = int(callback.data.split(":")[2])
    acc = await db.get_account(acc_id)
    if not acc:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    status_icon = "✅ Активен" if acc["status"] == "active" else "❌ Деактивирован"
    text = (
        f"<b>👤 Аккаунт #{acc_id}</b>\n\n"
        f"Имя: <b>{acc['first_name'] or '—'}</b>\n"
        f"Username: @{acc['username'] or '—'}\n"
        f"User ID: <code>{acc['tg_id'] or '—'}</code>\n"
        f"Телефон: <code>+{acc['phone'] or '—'}</code>\n"
        f"DC: {acc['dc_id'] or '—'}\n"
        f"Статус: {status_icon}\n"
        f"Добавлен: {(acc['added_at'] or '')[:16]}"
    )
    await callback.message.edit_text(text, reply_markup=kb.account_detail(acc_id, acc["status"]))


@router.callback_query(F.data.startswith("acc:activate:") | F.data.startswith("acc:deactivate:"))
async def cb_acc_toggle(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    parts = callback.data.split(":")
    action, acc_id = parts[1], int(parts[2])
    new_status = "active" if action == "activate" else "inactive"
    await db.set_account_status(acc_id, new_status)
    await callback.answer(f"Статус обновлён: {new_status}")
    acc = await db.get_account(acc_id)
    if not acc:
        return
    status_icon = "✅ Активен" if acc["status"] == "active" else "❌ Деактивирован"
    text = (
        f"<b>👤 Аккаунт #{acc_id}</b>\n\n"
        f"Имя: <b>{acc['first_name'] or '—'}</b>\n"
        f"Username: @{acc['username'] or '—'}\n"
        f"Статус: {status_icon}"
    )
    await callback.message.edit_text(text, reply_markup=kb.account_detail(acc_id, acc["status"]))


@router.callback_query(F.data.startswith("acc:delete:"))
async def cb_acc_delete(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    acc_id = int(callback.data.split(":")[2])
    await db.delete_account(acc_id)
    await callback.answer("Аккаунт удалён из БД")
    accounts = await db.get_accounts()
    await callback.message.edit_text(
        f"<b>⚡ Аккаунты</b>\n\nВсего: {len(accounts)}",
        reply_markup=kb.accounts_list(accounts),
    )
