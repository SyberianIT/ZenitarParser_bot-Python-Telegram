"""
Two modes:
  • mailer:bot      — send via the bot to everyone in bot_subs (who /start'd)
  • mailer:accounts — send DMs via Pyrogram accounts to parsed users
  • menu:broadcast  — alias for mailer:bot
"""
import asyncio
import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import db
import kb
import engine
import shared
from states import MailerSG, BotBroadcastSG
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()


def _admin(uid): return uid == ADMIN_ID


def _bar(cur, total, w=14):
    if not total:
        return "▱" * w
    f = round(w * cur / total)
    return "▰" * f + "▱" * (w - f)


# ── Mailer menu ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:mailer")
async def cb_mailer_menu(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    subs_count = await db.count_bot_subs()
    await callback.message.edit_text(
        "<b>💌 Рассыльщик</b>\n\nВыберите режим:",
        reply_markup=kb.mailer_menu(subs_count),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  BOT BROADCAST
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"menu:broadcast", "mailer:bot"}))
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    subs = await db.get_bot_subs()
    if not subs:
        await callback.answer("Нет подписчиков бота.", show_alert=True)
        return
    await state.set_state(BotBroadcastSG.message)
    await callback.answer()
    await callback.message.edit_text(
        f"<b>🤖 Бот-рассылка</b>\n\n"
        f"Подписчиков: <b>{len(subs)}</b>\n\n"
        f"Введи текст сообщения (поддерживается HTML):",
        reply_markup=kb.back("mailer"),
    )


@router.message(BotBroadcastSG.message)
async def bcast_got_message(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    await state.update_data(text=message.html_text, media_id=None, media_type=None)
    await state.set_state(BotBroadcastSG.media)
    await message.reply(
        "<b>🖼 Прикрепи медиа</b>\n\n"
        "Отправь фото, видео или документ.\n"
        "Или нажми <i>Без медиа</i>:",
        reply_markup=kb.skip_media(),
    )


@router.message(BotBroadcastSG.media, F.photo | F.video | F.document)
async def bcast_got_media(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"
    else:
        media_id = message.document.file_id
        media_type = "document"
    await state.update_data(media_id=media_id, media_type=media_type)
    await _bcast_confirm(message, state)


@router.callback_query(BotBroadcastSG.media, F.data == "media:skip")
async def bcast_skip_media(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    await _bcast_confirm(callback.message, state, edit=True)


async def _bcast_confirm(msg, state: FSMContext, edit=False):
    data = await state.get_data()
    text = data.get("text", "")
    media_type = data.get("media_type")
    subs = await db.get_bot_subs()
    preview = text[:200] + ("…" if len(text) > 200 else "")
    body = (
        f"<b>✅ Подтвердить рассылку</b>\n\n"
        f"Получателей: <b>{len(subs)}</b>\n"
        f"Медиа: {media_type or 'нет'}\n\n"
        f"<b>Сообщение:</b>\n{preview}"
    )
    await state.set_state(BotBroadcastSG.confirm)
    if edit:
        await msg.edit_text(body, reply_markup=kb.confirm_send("Разослать"))
    else:
        await msg.reply(body, reply_markup=kb.confirm_send("Разослать"))


@router.callback_query(BotBroadcastSG.confirm, F.data == "send:confirm")
async def bcast_execute(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    text = data["text"]
    media_id = data.get("media_id")
    media_type = data.get("media_type")
    subs = await db.get_bot_subs()

    uid = callback.from_user.id
    stop = shared.acquire(uid)

    prog = await callback.message.edit_text(
        f"<b>🤖 Рассылка запущена</b>\n\n"
        f"0/{len(subs)}\n⏳ Начинаю…",
        reply_markup=kb.cancel_job(),
    )

    sent = failed = 0
    for i, sub in enumerate(subs):
        if stop.is_set():
            break
        try:
            tid = sub["tg_id"]
            if media_id and media_type == "photo":
                await bot.send_photo(tid, media_id, caption=text)
            elif media_id and media_type == "video":
                await bot.send_video(tid, media_id, caption=text)
            elif media_id and media_type == "document":
                await bot.send_document(tid, media_id, caption=text)
            else:
                await bot.send_message(tid, text)
            sent += 1
        except Exception as e:
            failed += 1
            log.warning(f"Bot broadcast to {sub['tg_id']}: {e}")

        if (i + 1) % 10 == 0 or i + 1 == len(subs):
            try:
                bar = _bar(i + 1, len(subs))
                await prog.edit_text(
                    f"<b>🤖 Рассылка через бота</b>\n\n"
                    f"{bar} {i+1}/{len(subs)}\n"
                    f"✅ Отправлено: <b>{sent}</b>\n"
                    f"❌ Ошибок: <b>{failed}</b>",
                    reply_markup=kb.cancel_job(),
                )
            except Exception:
                pass
        await asyncio.sleep(0.05)

    shared.release(uid)
    stopped = stop.is_set()
    icon = "⛔" if stopped else "✅"
    await prog.edit_text(
        f"<b>{icon} Рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>\n"
        f"📊 Всего: {len(subs)}",
        reply_markup=kb.back(),
    )
    await db.save_campaign("Бот-рассылка", "bot", None, text, media_id, media_type, None, 0.05, sent, failed, len(subs))


# ═══════════════════════════════════════════════════════════════════════════════
#  ACCOUNT DM
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "mailer:accounts")
async def cb_dm_select_result(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    results = await db.get_results()
    if not results:
        await callback.message.edit_text(
            "<b>💌 DM через аккаунты</b>\n\n⚠️ Нет сохранённых результатов парсинга.",
            reply_markup=kb.back("mailer"),
        )
        return
    await callback.message.edit_text(
        "<b>💌 DM через аккаунты</b>\n\nВыбери список получателей:",
        reply_markup=kb.results_list(results),
    )
    await state.set_state(MailerSG.result)


@router.callback_query(MailerSG.result, F.data.startswith("result:view:"))
async def cb_dm_result_chosen(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    rid = int(callback.data.split(":")[2])
    await state.update_data(result_id=rid)
    await state.set_state(MailerSG.message)
    await callback.answer()
    r = await db.get_result(rid)
    await callback.message.edit_text(
        f"<b>💌 DM через аккаунты</b>\n\n"
        f"Список: <b>{r['name'] if r else rid}</b> ({r['total'] if r else '?'} получателей)\n\n"
        f"Введи текст сообщения (поддерживается HTML):",
        reply_markup=kb.back("mailer"),
    )


# Shortcut from result detail
@router.callback_query(F.data.startswith("result:dm:"))
async def cb_dm_from_result(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    rid = int(callback.data.split(":")[2])
    await state.update_data(result_id=rid)
    await state.set_state(MailerSG.message)
    await callback.answer()
    r = await db.get_result(rid)
    await callback.message.edit_text(
        f"<b>💌 DM через аккаунты</b>\n\n"
        f"Список: <b>{r['name'] if r else rid}</b>\n\n"
        f"Введи текст сообщения:",
        reply_markup=kb.back("mailer"),
    )


@router.message(MailerSG.message)
async def dm_got_message(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    await state.update_data(text=message.html_text, media_id=None, media_type=None, media_path=None)
    await state.set_state(MailerSG.media)
    await message.reply(
        "<b>🖼 Прикрепи медиа</b>\n\n"
        "Отправь фото, видео или документ, или нажми <i>Без медиа</i>:",
        reply_markup=kb.skip_media(),
    )


@router.message(MailerSG.media, F.photo | F.video | F.document)
async def dm_got_media(message: Message, state: FSMContext, bot: Bot):
    if not _admin(message.from_user.id):
        return
    if message.photo:
        fid = message.photo[-1].file_id
        mtype = "photo"
        ext = "jpg"
    elif message.video:
        fid = message.video.file_id
        mtype = "video"
        ext = "mp4"
    else:
        fid = message.document.file_id
        mtype = "document"
        ext = "bin"

    await state.update_data(media_id=fid, media_type=mtype)

    # Download for use with Pyrogram
    path = f"tmp_media_{message.from_user.id}.{ext}"
    try:
        await bot.download(fid, destination=path)
        await state.update_data(media_path=path)
    except Exception as e:
        log.error(f"Media download: {e}")

    await _dm_go_accounts(message, state)


@router.callback_query(MailerSG.media, F.data == "media:skip")
async def dm_skip_media(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    await _dm_go_accounts(callback.message, state, edit=True)


async def _dm_go_accounts(msg, state: FSMContext, edit=False):
    await state.set_state(MailerSG.accounts)
    accounts = await db.get_accounts(active_only=True)
    if not accounts:
        body = "❌ Нет активных аккаунтов."
        if edit:
            await msg.edit_text(body, reply_markup=kb.back("mailer"))
        else:
            await msg.reply(body, reply_markup=kb.back("mailer"))
        return
    await state.update_data(selected_accounts=[])
    body = "<b>⚡ Выбери аккаунты для рассылки:</b>"
    if edit:
        await msg.edit_text(body, reply_markup=kb.account_select(accounts, []))
    else:
        await msg.reply(body, reply_markup=kb.account_select(accounts, []))


@router.callback_query(MailerSG.accounts, F.data.startswith("acc:toggle:"))
async def dm_toggle_acc(callback: CallbackQuery, state: FSMContext):
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


@router.callback_query(MailerSG.accounts, F.data == "acc:done")
async def dm_acc_done(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    data = await state.get_data()
    if not data.get("selected_accounts"):
        await callback.answer("⚠️ Выбери хотя бы один аккаунт!", show_alert=True)
        return
    await state.set_state(MailerSG.delay)
    await callback.answer()
    await callback.message.edit_text(
        "<b>⏱ Задержка между сообщениями</b>\n\nВведи задержку в секундах (рекомендуется 10–60):",
        reply_markup=kb.back("mailer"),
    )


@router.message(MailerSG.delay)
async def dm_got_delay(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    try:
        delay = float(message.text.strip().replace(",", "."))
        delay = max(1.0, min(delay, 600.0))
    except ValueError:
        await message.reply("❌ Введи число. Например: <code>15</code>")
        return
    await state.update_data(delay=delay)
    await state.set_state(MailerSG.confirm)
    data = await state.get_data()
    r = await db.get_result(data["result_id"])
    text_preview = (data.get("text") or "")[:150]
    await message.reply(
        f"<b>✅ Подтверди DM-рассылку</b>\n\n"
        f"Список: <b>{r['name'] if r else '?'}</b> ({r['total'] if r else '?'} чел.)\n"
        f"Аккаунтов: {len(data['selected_accounts'])}\n"
        f"Задержка: {delay}с\n"
        f"Медиа: {data.get('media_type') or 'нет'}\n\n"
        f"<b>Сообщение:</b>\n{text_preview}{'…' if len(data.get('text',''))>150 else ''}",
        reply_markup=kb.confirm_send("Начать рассылку"),
    )


@router.callback_query(MailerSG.confirm, F.data == "send:confirm")
async def dm_execute(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    rid = data["result_id"]
    text = data.get("text", "")
    media_path = data.get("media_path")
    media_type = data.get("media_type")
    delay = data.get("delay", 15.0)
    acc_ids = data.get("selected_accounts", [])

    users = await db.get_parsed(rid, users_only=True)
    targets = [u["tg_id"] for u in users if u.get("tg_id")]
    if not targets:
        # fallback: try usernames
        targets = [u["username"] for u in users if u.get("username")]

    if not targets:
        await callback.message.edit_text("❌ Нет целевых пользователей в результате.", reply_markup=kb.back())
        return

    accounts = [await db.get_account(i) for i in acc_ids]
    accounts = [a for a in accounts if a and a["status"] == "active"]
    if not accounts:
        await callback.message.edit_text("❌ Активные аккаунты не найдены.", reply_markup=kb.back())
        return

    uid = callback.from_user.id
    stop = shared.acquire(uid)

    prog = await callback.message.edit_text(
        f"<b>💌 DM-рассылка запущена</b>\n\n"
        f"👤 Всего: {len(targets)}\n"
        f"⚡ Аккаунтов: {len(accounts)}\n"
        f"⏳ Начинаю…",
        reply_markup=kb.cancel_job(),
    )

    total_sent = total_failed = 0
    per_account = (len(targets) + len(accounts) - 1) // len(accounts)

    for idx, acc in enumerate(accounts):
        if stop.is_set():
            break
        chunk = targets[idx * per_account: (idx + 1) * per_account]
        if not chunk:
            break

        async def cb(i=0, total=0, sent=0, failed=0, flood_wait=0, acc_name=acc["first_name"] or acc["username"]):
            if flood_wait:
                txt = f"<b>⏳ FloodWait {flood_wait}с</b>"
            else:
                bar = _bar(i, total)
                txt = (
                    f"<b>💌 DM-рассылка</b>\n\n"
                    f"{bar} {i}/{total}\n"
                    f"📤 Аккаунт: <b>{acc_name}</b>\n"
                    f"✅ Отправлено: <b>{total_sent + sent}</b>\n"
                    f"❌ Ошибок: <b>{total_failed + failed}</b>"
                )
            try:
                await prog.edit_text(txt, reply_markup=kb.cancel_job())
            except Exception:
                pass

        s, f = await engine.send_dms(
            acc["session_name"], chunk, text,
            media_path, media_type, delay, stop, cb,
        )
        total_sent += s
        total_failed += f

    shared.release(uid)

    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except Exception:
            pass

    stopped = stop.is_set()
    icon = "⛔" if stopped else "✅"
    await prog.edit_text(
        f"<b>{icon} DM-рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{total_sent}</b>\n"
        f"❌ Ошибок: <b>{total_failed}</b>\n"
        f"📊 Всего целей: {len(targets)}",
        reply_markup=kb.back(),
    )
    await db.save_campaign(
        "DM-рассылка", "accounts", rid, text,
        data.get("media_id"), media_type, acc_ids, delay,
        total_sent, total_failed, len(targets),
    )

