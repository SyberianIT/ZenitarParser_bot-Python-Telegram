import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import db
import kb
import engine
import shared
from states import ParserSG
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()

_temp: dict[int, dict] = {}


def _admin(uid): return uid == ADMIN_ID


def _bar(cur: int, total: int, w=14) -> str:
    if not total:
        return "▱" * w
    f = round(w * cur / total)
    return "▰" * f + "▱" * (w - f)


# ── Menu ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:parser")
async def cb_parser_menu(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    accounts = await db.get_accounts(active_only=True)
    if not accounts:
        await callback.message.edit_text(
            "<b>⚠️ Нет активных аккаунтов</b>\n\n"
            "Добавь .session файлы в папку <code>sessions/</code> и обнови список в разделе ⚡ Аккаунты.",
            reply_markup=kb.back(),
        )
        return
    await callback.message.edit_text(
        "<b>🔍 Парсер</b>\n\nВыберите режим парсинга:",
        reply_markup=kb.parser_menu(),
    )


# ── Keyword parser ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "parser:keywords")
async def cb_kw_start(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await state.set_state(ParserSG.keywords)
    await callback.answer()
    await callback.message.edit_text(
        "<b>🔑 Поиск по ключевым словам</b>\n\n"
        "Введите ключевые слова — каждое с новой строки:\n\n"
        "<i>Пример:</i>\n<code>криптовалюта\nновости\nинвестиции</code>",
        reply_markup=kb.back("parser"),
    )


@router.message(ParserSG.keywords)
async def handle_keywords(message: Message, state: FSMContext, bot: Bot):
    if not _admin(message.from_user.id):
        return
    tags = [t.strip() for t in message.text.strip().splitlines() if t.strip()]
    if not tags:
        await message.reply("❌ Введи хотя бы одно ключевое слово.")
        return

    accounts = await db.get_accounts(active_only=True)
    if not accounts:
        await message.reply("❌ Нет активных аккаунтов.")
        return

    session = accounts[0]["session_name"]
    uid = message.from_user.id
    stop = shared.acquire(uid)

    prog = await message.reply(
        f"<b>🔑 Парсинг по ключевым словам</b>\n\n"
        f"{_bar(0, len(tags))} 0/{len(tags)}\n"
        f"▶️ Запускаю…",
        reply_markup=kb.cancel_parse(),
    )
    await state.clear()

    results = []

    async def cb(i=0, total=0, current="", found=0, flood_wait=0):
        if flood_wait:
            txt = f"<b>⏳ FloodWait {flood_wait}с</b>\nПродолжу автоматически…"
        else:
            txt = (
                f"<b>🔑 Парсинг по ключевым словам</b>\n\n"
                f"{_bar(i, total)} {i}/{total}\n"
                f"▶️ Сейчас: <b>{current}</b>\n"
                f"📦 Найдено: {found}"
            )
        try:
            await prog.edit_text(txt, reply_markup=kb.cancel_parse())
        except Exception:
            pass

    try:
        results = await engine.parse_keywords(session, tags, stop, cb)
    except Exception as e:
        await prog.edit_text(f"<b>❌ Ошибка парсинга</b>\n\n<code>{e}</code>", reply_markup=kb.back())
        shared.release(uid)
        return

    shared.release(uid)

    if not results:
        await prog.edit_text("❌ Ничего не найдено.", reply_markup=kb.back())
        return

    unique = list({r["username"]: r for r in results}.values())
    _temp[uid] = {"results": unique, "mode": "keyword", "source": ", ".join(tags[:3])}
    await prog.edit_text(
        f"<b>✅ Готово!</b>\n\n"
        f"📊 Найдено чатов: <b>{len(unique)}</b>\n\n"
        f"Введи название для сохранения результата:",
        reply_markup=kb.back(),
    )
    await state.set_state(ParserSG.result_name)


# ── Group members parser ───────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"parser:members", "parser:admins"}))
async def cb_group_start(callback: CallbackQuery, state: FSMContext):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    mode = "members" if callback.data == "parser:members" else "admins"
    await state.update_data(parse_mode=mode)
    await state.set_state(ParserSG.group_link)
    await callback.answer()
    label = "участников группы" if mode == "members" else "администраторов"
    await callback.message.edit_text(
        f"<b>{'👥' if mode == 'members' else '👑'} Парсинг {label}</b>\n\n"
        "Введи username или ссылку на группу/канал:\n\n"
        "<i>Пример: <code>@mychat</code> или <code>https://t.me/mychat</code></i>",
        reply_markup=kb.back("parser"),
    )


@router.message(ParserSG.group_link)
async def handle_group_link(message: Message, state: FSMContext, bot: Bot):
    if not _admin(message.from_user.id):
        return
    data = await state.get_data()
    mode = data.get("parse_mode", "members")

    raw = message.text.strip()
    group = raw.replace("https://t.me/", "").strip("/").strip()
    if not group.startswith("@"):
        group = "@" + group

    accounts = await db.get_accounts(active_only=True)
    if not accounts:
        await message.reply("❌ Нет активных аккаунтов.")
        return

    session = accounts[0]["session_name"]
    uid = message.from_user.id
    stop = shared.acquire(uid)

    label = "участников" if mode == "members" else "администраторов"
    prog = await message.reply(
        f"<b>{'👥' if mode == 'members' else '👑'} Парсинг {label}</b>\n\n"
        f"Группа: <code>{group}</code>\n"
        f"⏳ Подключаюсь…",
        reply_markup=kb.cancel_parse(),
    )
    await state.clear()

    results = []

    async def cb(offset=0, found=0, group="", flood_wait=0):
        if flood_wait:
            txt = f"<b>⏳ FloodWait {flood_wait}с</b>"
        else:
            txt = (
                f"<b>{'👥' if mode == 'members' else '👑'} Парсинг {label}</b>\n\n"
                f"📦 Собрано: <b>{found}</b>\n"
                f"🔄 Обработано позиций: {offset}"
            )
        try:
            await prog.edit_text(txt, reply_markup=kb.cancel_parse())
        except Exception:
            pass

    try:
        if mode == "members":
            results = await engine.parse_group_members(session, group, stop, cb)
        else:
            results = await engine.parse_channel_admins(session, group, stop, cb)
    except Exception as e:
        await prog.edit_text(
            f"<b>❌ Ошибка</b>\n\n<code>{str(e)[:300]}</code>\n\n"
            "<i>Убедись, что аккаунт является участником группы.</i>",
            reply_markup=kb.back(),
        )
        shared.release(uid)
        return

    shared.release(uid)

    if not results:
        await prog.edit_text("❌ Участники не найдены.", reply_markup=kb.back())
        return

    unique = list({r["id"]: r for r in results}.values())
    with_uname = sum(1 for r in unique if r.get("username"))
    _temp[uid] = {"results": unique, "mode": mode, "source": group}
    await prog.edit_text(
        f"<b>✅ Готово!</b>\n\n"
        f"📊 Всего: <b>{len(unique)}</b>\n"
        f"👤 С username: <b>{with_uname}</b>\n\n"
        f"Введи название для сохранения результата:",
        reply_markup=kb.back(),
    )
    await state.set_state(ParserSG.result_name)


# ── Save result ────────────────────────────────────────────────────────────────

@router.message(ParserSG.result_name)
async def handle_result_name(message: Message, state: FSMContext):
    if not _admin(message.from_user.id):
        return
    uid = message.from_user.id
    name = message.text.strip()[:80]
    tmp = _temp.pop(uid, None)
    if not tmp:
        await message.reply("❌ Данные парсинга не найдены. Начни заново.")
        await state.clear()
        return
    rid = await db.save_result(name, tmp["source"], tmp["mode"], tmp["results"])
    await state.clear()
    await message.reply(
        f"<b>💾 Результат сохранён</b>\n\n"
        f"📋 Название: <b>{name}</b>\n"
        f"📊 Записей: <b>{len(tmp['results'])}</b>\n"
        f"🆔 ID: {rid}",
        reply_markup=kb.back(),
    )

