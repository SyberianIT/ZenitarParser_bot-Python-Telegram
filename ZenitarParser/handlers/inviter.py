import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import db
import kb
import engine
import shared
from states import InviterSG
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()


def _admin(uid): return uid == ADMIN_ID


@router.callback_query(F.data == "menu:inviter")
async def cb_inviter_menu(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    results = await db.get_results()
    user_results = [r for r in results if r["mode"] in ("members", "admins")]
    if not user_results:
        await callback.message.edit_text(
            "<b>👥 Инвайтер</b>\n\n"
            "⚠️ Нет результатов с пользователями.\n"
            "Сначала запусти парсинг участников группы.",
            reply_markup=kb.back(),
        )
        return
    await callback.message.edit_text(
        "<b>👥 Инвайтер</b>\n\nВыбери список пользователей для инвайта:",
        reply_markup=kb.results_list(user_results),
    )


@router.callback_query(F.data.startswith("result:invite:"))
async def cb_select_result(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    rid = int(callback.data.split(":")[2])
    r = await db.get_result(rid)
    if not r:
        await callback.answer("Результат не найден", show_alert=True)
        return
    await state.update_data(result_id=rid)
    await state.set_state(InviterSG.target)
    await callback.answer()
    users = await db.get_parsed(rid, users_only=True, with_username=True)
    await callback.message.edit_text(
        f"<b>👥 Инвайтер</b>\n\n"
        f"Список: <b>{r['name']}</b> ({len(users)} пользователей с username)\n\n"
        f"Введи username или ссылку <b>целевой группы</b>:\n"
        f"<i>Пример: @mygroup</i>",
        reply_markup=kb.back(),
    )


@router.message(InviterSG.target)
async def handle_target(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    raw = message.text.strip().replace("https://t.me/", "").strip("/")
    group = raw if raw.startswith("@") else "@" + raw
    await state.update_data(target_group=group)
    await state.set_state(InviterSG.delay)
    await message.reply(
        f"<b>⏱ Задержка между инвайтами</b>\n\n"
        f"Цель: <code>{group}</code>\n\n"
        f"Введи задержку в секундах (рекомендуется 5–15):",
        reply_markup=kb.back(),
    )


@router.message(InviterSG.delay)
async def handle_delay(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    try:
        delay = float(message.text.strip().replace(",", "."))
        delay = max(1.0, min(delay, 300.0))
    except ValueError:
        await message.reply("❌ Введи число. Например: <code>10</code>")
        return
    await state.update_data(delay=delay)
    await state.set_state(InviterSG.accounts)
    accounts = await db.get_accounts(active_only=True)
    if not accounts:
        await message.reply("❌ Нет активных аккаунтов.", reply_markup=kb.back())
        await state.clear()
        return
    await state.update_data(selected_accounts=[])
    await message.reply(
        f"<b>⚡ Выбери аккаунты для инвайта</b>\n\nЗадержка: {delay}с",
        reply_markup=kb.account_select(accounts, []),
    )


@router.callback_query(InviterSG.accounts, F.data.startswith("acc:toggle:"))
async def cb_toggle_acc(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    acc_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected = list(data.get("selected_accounts", []))
    if acc_id in selected:
        selected.remove(acc_id)
    else:
        selected.append(acc_id)
    await state.update_data(selected_accounts=selected)
    accounts = await db.get_accounts(active_only=True)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=kb.account_select(accounts, selected))


@router.callback_query(InviterSG.accounts, F.data == "acc:done")
async def cb_acc_done(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    data = await state.get_data()
    selected = data.get("selected_accounts", [])
    if not selected:
        await callback.answer("⚠️ Выбери хотя бы один аккаунт!", show_alert=True)
        return
    rid = data["result_id"]
    target = data["target_group"]
    delay = data["delay"]
    r = await db.get_result(rid)
    await callback.answer()
    await callback.message.edit_text(
        f"<b>👥 Подтверди инвайт</b>\n\n"
        f"Список: <b>{r['name'] if r else rid}</b>\n"
        f"Цель: <code>{target}</code>\n"
        f"Аккаунтов: {len(selected)}\n"
        f"Задержка: {delay}с",
        reply_markup=kb.confirm_send("Начать инвайт"),
    )
    await state.set_state(InviterSG.confirm)


@router.callback_query(InviterSG.confirm, F.data == "send:confirm")
async def cb_invite_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    rid = data["result_id"]
    target = data["target_group"]
    delay = data["delay"]
    acc_ids = data["selected_accounts"]

    users = await db.get_parsed(rid, users_only=True, with_username=True)
    identifiers = [u["username"] for u in users if u.get("username")]

    if not identifiers:
        await callback.message.edit_text("❌ Нет пользователей с username для инвайта.", reply_markup=kb.back())
        return

    accounts = [await db.get_account(i) for i in acc_ids]
    accounts = [a for a in accounts if a]
    session = accounts[0]["session_name"]

    uid = callback.from_user.id
    stop = shared.acquire(uid)

    prog = await callback.message.edit_text(
        f"<b>👥 Инвайт запущен</b>\n\n"
        f"👤 Всего: {len(identifiers)}\n"
        f"📡 Цель: <code>{target}</code>\n"
        f"⏳ Начинаю…",
        reply_markup=kb.cancel_job(),
    )

    async def cb(i=0, total=0, invited=0, failed=0, flood_wait=0):
        if flood_wait:
            txt = f"<b>⏳ FloodWait {flood_wait}с</b>"
        else:
            bar = _bar(i, total)
            txt = (
                f"<b>👥 Инвайт</b>\n\n"
                f"{bar} {i}/{total}\n"
                f"✅ Добавлено: <b>{invited}</b>\n"
                f"❌ Ошибок: <b>{failed}</b>"
            )
        try:
            await prog.edit_text(txt, reply_markup=kb.cancel_job())
        except Exception:
            pass

    def _bar(cur, total, w=14):
        if not total:
            return "▱" * w
        f = round(w * cur / total)
        return "▰" * f + "▱" * (w - f)

    try:
        invited, failed = await engine.invite_users(session, target, identifiers, delay, stop, cb)
    except Exception as e:
        await prog.edit_text(f"<b>❌ Ошибка инвайта</b>\n\n<code>{e}</code>", reply_markup=kb.back())
        shared.release(uid)
        return

    shared.release(uid)
    await db.save_invite_job(rid, target, acc_ids, delay, invited, failed, len(identifiers))

    stopped = stop.is_set()
    icon = "⛔" if stopped else "✅"
    await prog.edit_text(
        f"<b>{icon} Инвайт завершён</b>\n\n"
        f"✅ Добавлено: <b>{invited}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>\n"
        f"📊 Всего попыток: {invited + failed}",
        reply_markup=kb.back(),
    )

