"""Resilient message helpers.

Telegram's legacy *Markdown* parse mode rejects a whole message when dynamic
content contains unbalanced control characters (`_`, `*`, `` ` ``). This is
common in practice: bot usernames frequently contain underscores
(e.g. ``my_cool_bot``) and target group names / account first-names can too.

These helpers try the requested (Markdown) render first and, on a parse error,
transparently fall back to plain text so the user still sees the content
instead of nothing.
"""
import logging

from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def safe_edit(message, text: str, **kwargs):
    """Like ``message.edit_text`` but falls back to plain text on a parse error."""
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "parse" not in str(e).lower():
            # "message is not modified" and similar — nothing to recover from
            return None
        kwargs.pop("parse_mode", None)
        try:
            return await message.edit_text(text, parse_mode=None, **kwargs)
        except TelegramBadRequest:
            return None


async def safe_answer(message, text: str, **kwargs):
    """Like ``message.answer`` but falls back to plain text on a parse error."""
    try:
        return await message.answer(text, **kwargs)
    except TelegramBadRequest as e:
        if "parse" not in str(e).lower():
            raise
        kwargs.pop("parse_mode", None)
        return await message.answer(text, parse_mode=None, **kwargs)
