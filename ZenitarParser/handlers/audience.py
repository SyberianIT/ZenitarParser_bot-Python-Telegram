import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
from modules import audience as A
from utils.keyboards import audience_menu, audience_filter_menu, back_kb, done_kb
from utils.export import load_csv, to_csv
from handlers.start import admin

router = Router()


class AudienceState(StatesGroup):
    dedupe_file = State()
    merge_files = State()
    subtract_base = State()
    subtract_exclude = State()
    filter_file = State()


async def _download(message: Message, tag: str) -> list | None:
    if not (message.document and message.document.file_name.endswith(".csv")):
        await message.answer("❌ Ожидаю CSV файл.")
        return None
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    path = os.path.join(config.UPLOADS_DIR, f"aud_{tag}_{message.from_user.id}.csv")
    await message.bot.download(message.document, path)
    try:
        return await load_csv(path)
    except Exception as e:
        await message.answer(f"❌ Не удалось прочитать CSV: {str(e)[:100]}")
        return None


async def _send_result(message: Message, rows: list, label: str):
    if not rows:
        await message.answer("⚠️ Результат пуст.", reply_markup=back_kb("audience_menu"))
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = await to_csv(rows, f"{label}_{ts}.csv")
    await message.answer_document(
        FSInputFile(path),
        caption=f"✅ {label} | {len(rows)} записей",
    )


# ── Menu ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "audience_menu")
async def cb_audience_menu(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text(
        "🎯 *Аудитория*\n\n"
        "Операции над списками (CSV):\n"
        "• 🧹 *Дедупликация* — убрать повторы\n"
        "• ➕ *Объединить* — слить несколько списков\n"
        "• ➖ *Вычесть* — убрать из списка A всех из списка B "
        "(например, исключить уже приглашённых)\n"
        "• 🔬 *Фильтр* — только с @username / Premium / без ботов",
        reply_markup=audience_menu(), parse_mode="Markdown",
    )
    await cb.answer()


# ── Dedupe ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "aud_dedupe")
async def cb_dedupe(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(AudienceState.dedupe_file)
    await cb.message.edit_text("🧹 Отправьте CSV для дедупликации:", reply_markup=back_kb("audience_menu"))
    await cb.answer()


@router.message(AudienceState.dedupe_file, F.document)
async def do_dedupe(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    rows = await _download(message, "dd")
    if rows is None:
        return
    await state.clear()
    result = A.dedupe(rows)
    await message.answer(f"🧹 Было: {len(rows)} → стало: {len(result)} (убрано {len(rows) - len(result)})")
    await _send_result(message, result, "dedupe")


# ── Merge ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "aud_merge")
async def cb_merge(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(AudienceState.merge_files)
    await state.update_data(merge_rows=[])
    await cb.message.edit_text(
        "➕ Отправляйте CSV файлы по одному.\n"
        "Когда закончите — нажмите *Готово*.",
        parse_mode="Markdown", reply_markup=done_kb("aud_merge_done", "audience_menu"),
    )
    await cb.answer()


@router.message(AudienceState.merge_files, F.document)
async def do_merge_add(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    rows = await _download(message, "mg")
    if rows is None:
        return
    data = await state.get_data()
    acc = data.get("merge_rows", [])
    acc.append(rows)
    await state.update_data(merge_rows=acc)
    total = sum(len(x) for x in acc)
    await message.answer(
        f"📥 Файлов: {len(acc)} · строк всего: {total}\nДобавьте ещё или нажмите *Готово*.",
        parse_mode="Markdown", reply_markup=done_kb("aud_merge_done", "audience_menu"),
    )


@router.callback_query(F.data == "aud_merge_done")
async def cb_merge_done(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    data = await state.get_data()
    lists = data.get("merge_rows", [])
    await state.clear()
    if not lists:
        await cb.answer("Не загружено ни одного файла", show_alert=True)
        return
    result = A.merge(*lists)
    await cb.message.edit_text(
        f"➕ Объединено {len(lists)} файлов → {len(result)} уникальных записей.",
        reply_markup=back_kb("audience_menu"),
    )
    await _send_result(cb.message, result, "merged")
    await cb.answer()


# ── Subtract ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "aud_subtract")
async def cb_subtract(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(AudienceState.subtract_base)
    await cb.message.edit_text(
        "➖ *Шаг 1/2.* Отправьте *основной* список (из кого вычитаем):",
        parse_mode="Markdown", reply_markup=back_kb("audience_menu"),
    )
    await cb.answer()


@router.message(AudienceState.subtract_base, F.document)
async def do_subtract_base(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    rows = await _download(message, "sb")
    if rows is None:
        return
    await state.update_data(base=rows)
    await state.set_state(AudienceState.subtract_exclude)
    await message.answer(
        f"✅ Основной список: {len(rows)}.\n\n"
        "*Шаг 2/2.* Отправьте список для *исключения*:",
        parse_mode="Markdown",
    )


@router.message(AudienceState.subtract_exclude, F.document)
async def do_subtract_exclude(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    exclude = await _download(message, "se")
    if exclude is None:
        return
    data = await state.get_data()
    base = data.get("base", [])
    await state.clear()
    result = A.subtract(base, exclude)
    await message.answer(
        f"➖ {len(base)} − {len(exclude)} → осталось {len(result)} записей."
    )
    await _send_result(message, result, "subtracted")


# ── Filter ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "aud_filter")
async def cb_filter(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    await state.set_state(AudienceState.filter_file)
    await cb.message.edit_text("🔬 Отправьте CSV для фильтрации:", reply_markup=back_kb("audience_menu"))
    await cb.answer()


@router.message(AudienceState.filter_file, F.document)
async def do_filter_file(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    rows = await _download(message, "fl")
    if rows is None:
        return
    await state.update_data(filter_rows=rows)
    await message.answer(
        f"✅ Загружено {len(rows)}. Выберите фильтр:",
        reply_markup=audience_filter_menu(),
    )


@router.callback_query(F.data.startswith("af_"))
async def cb_apply_filter(cb: CallbackQuery, state: FSMContext):
    if not admin(cb.from_user.id): return
    mode = cb.data[3:]
    data = await state.get_data()
    rows = data.get("filter_rows", [])
    await state.clear()
    if not rows:
        await cb.answer("Сначала загрузите файл", show_alert=True)
        return
    result = A.apply_filter(rows, mode)
    labels = {
        "only_username": "с @username", "only_premium": "Premium",
        "no_bots": "без ботов", "only_humans": "только люди",
    }
    await cb.message.edit_text(
        f"🔬 Фильтр «{labels.get(mode, mode)}»: {len(rows)} → {len(result)}",
        reply_markup=back_kb("audience_menu"),
    )
    await _send_result(cb.message, result, f"filtered_{mode}")
    await cb.answer()


# Wrong-type guards
@router.message(AudienceState.dedupe_file)
@router.message(AudienceState.merge_files)
@router.message(AudienceState.subtract_base)
@router.message(AudienceState.subtract_exclude)
@router.message(AudienceState.filter_file)
async def wrong_input(message: Message):
    if not admin(message.from_user.id): return
    await message.answer("❌ Ожидаю CSV файл.")
