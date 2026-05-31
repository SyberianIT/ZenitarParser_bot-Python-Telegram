import csv
import io
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile

import db
import kb
from config import ADMIN_ID

log = logging.getLogger(__name__)
router = Router()


def _admin(uid): return uid == ADMIN_ID


MODE_LABEL = {"keyword": "🔑 Ключевые слова", "members": "👥 Участники", "admins": "👑 Администраторы"}


@router.callback_query(F.data == "menu:results")
async def cb_results(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    results = await db.get_results()
    if not results:
        await callback.message.edit_text(
            "<b>📊 Результаты</b>\n\n<i>Нет сохранённых результатов.</i>",
            reply_markup=kb.back(),
        )
        return
    await callback.message.edit_text(
        f"<b>📊 Результаты</b> — {len(results)} шт.\n\nВыбери результат:",
        reply_markup=kb.results_list(results),
    )


@router.callback_query(F.data.startswith("result:view:"))
async def cb_result_view(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()
    rid = int(callback.data.split(":")[2])
    r = await db.get_result(rid)
    if not r:
        await callback.answer("Результат не найден", show_alert=True)
        return
    users = await db.get_parsed(rid)
    with_uname = sum(1 for u in users if u.get("username"))
    mode = MODE_LABEL.get(r["mode"], r["mode"])
    text = (
        f"<b>📋 {r['name']}</b>\n\n"
        f"Режим: {mode}\n"
        f"Источник: <code>{r['source'] or '—'}</code>\n"
        f"Всего: <b>{r['total']}</b>\n"
        f"С username: <b>{with_uname}</b>\n"
        f"Дата: {(r['created_at'] or '')[:16]}"
    )
    await callback.message.edit_text(text, reply_markup=kb.result_detail(rid))


@router.callback_query(F.data.startswith("result:csv:"))
async def cb_csv(callback: CallbackQuery, bot: Bot):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer("📥 Генерирую CSV…")
    rid = int(callback.data.split(":")[2])
    r = await db.get_result(rid)
    users = await db.get_parsed(rid)
    if not users:
        await callback.answer("Нет данных", show_alert=True)
        return

    buf = io.StringIO()
    buf.write("﻿")  # BOM for Excel
    w = csv.writer(buf)

    if r and r["mode"] == "keyword":
        w.writerow(["Username", "Источник"])
        w.writerow(["", r.get("source", "")])
        w.writerow([])
        w.writerow(["Username"])
        for u in sorted(users, key=lambda x: x.get("username") or ""):
            w.writerow([f"@{u['username']}" if u.get("username") else ""])
    else:
        w.writerow(["User ID", "Username", "Имя", "Фамилия", "Бот"])
        w.writerow(["", "", r.get("source", ""), "", ""])
        w.writerow([])
        w.writerow(["User ID", "Username", "Имя", "Фамилия", "Бот"])
        for u in users:
            w.writerow([
                u.get("tg_id", ""),
                f"@{u['username']}" if u.get("username") else "",
                u.get("first_name", ""),
                u.get("last_name", ""),
                "Да" if u.get("is_bot") else "Нет",
            ])

    name = f"{r['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv" if r else "export.csv"
    data = buf.getvalue().encode("utf-8-sig")
    await bot.send_document(
        callback.from_user.id,
        BufferedInputFile(data, filename=name),
        caption=f"<b>📥 {r['name'] if r else 'Экспорт'}</b>\n{len(users)} записей",
    )


@router.callback_query(F.data.startswith("result:delete:"))
async def cb_delete(callback: CallbackQuery):
    if not _admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    parts = callback.data.split(":")
    rid = int(parts[2])
    if len(parts) > 3 and parts[3] == "confirm":
        await db.delete_result(rid)
        await callback.answer("🗑 Удалено")
        results = await db.get_results()
        await callback.message.edit_text(
            f"<b>📊 Результаты</b> — {len(results)} шт.",
            reply_markup=kb.results_list(results) if results else kb.back(),
        )
    else:
        await callback.answer()
        r = await db.get_result(rid)
        await callback.message.edit_text(
            f"<b>🗑 Удалить результат?</b>\n\n{r['name'] if r else rid}",
            reply_markup=kb.confirm_delete(rid),
        )


# Inviter / mailer shortcuts from result detail are handled in inviter.py / mailer.py
