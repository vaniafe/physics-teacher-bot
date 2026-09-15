"""Доставка сообщений сайта -> Telegram и обработка удалений/правок.

Цикл каждые ~15 секунд:
1. Новые сообщения (от учителя и эхо ученика с сайта) -> в чат ученика.
2. Помеченные удалёнными -> удаляем из Telegram (если возможно) и из базы.
3. Комментарии к работам: отправка / правка / удаление.
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from services.supabase_client import (
    get_pending_messages, mark_message_delivered, get_student_by_id,
    get_deleted_messages, hard_delete_message,
    get_pending_comments, update_comment, hard_delete_comment,
)


def _fmt_comment_text(date_iso: str, text: str) -> str:
    try:
        d = datetime.strptime(str(date_iso)[:10], "%Y-%m-%d").strftime("%d.%m")
    except ValueError:
        d = str(date_iso)[:10]
    return f"💬 Комментарий учителя к домашнему заданию на {d}:\n{text}"


async def _tg_chat_id(student_id) -> int | None:
    st = await get_student_by_id(student_id)
    if st and st.get("telegram_id") and st["telegram_id"] > 0:
        return st["telegram_id"]
    return None


async def _deliver_messages(bot: Bot):
    for m in await get_pending_messages():
        chat_id = await _tg_chat_id(m["student_id"])
        if not chat_id:
            await mark_message_delivered(m["id"], None)
            continue
        try:
            sent = await bot.send_message(chat_id, m["text"])
            await mark_message_delivered(m["id"], sent.message_id)
        except Exception as e:
            logging.warning("Доставка сообщения %s не удалась: %s", m["id"], e)
            await mark_message_delivered(m["id"], None)  # не крутим бесконечно


async def _cleanup_deleted(bot: Bot):
    for m in await get_deleted_messages():
        if m.get("tg_message_id"):
            chat_id = await _tg_chat_id(m["student_id"])
            if chat_id:
                try:
                    await bot.delete_message(chat_id, m["tg_message_id"])
                except Exception:
                    pass  # старше 48 ч или чат недоступен — оставляем как есть
        await hard_delete_message(m["id"])


async def _handle_comments(bot: Bot):
    for c in await get_pending_comments():
        state_ = c["tg_state"]
        chat_id = await _tg_chat_id(c["student_id"])
        if not chat_id:
            if state_ == "delete":
                await hard_delete_comment(c["id"])
            else:
                await update_comment(c["id"], {"tg_state": "done"})
            continue
        try:
            if state_ == "send":
                sent = await bot.send_message(chat_id, _fmt_comment_text(c["date"], c["text"]))
                await update_comment(c["id"], {"tg_state": "done", "tg_message_id": sent.message_id})
            elif state_ == "edit":
                edited = False
                if c.get("tg_message_id"):
                    try:
                        await bot.edit_message_text(
                            _fmt_comment_text(c["date"], c["text"]),
                            chat_id=chat_id, message_id=c["tg_message_id"])
                        await update_comment(c["id"], {"tg_state": "done"})
                        edited = True
                    except Exception:
                        pass  # старше 48 ч — отправим новым сообщением
                if not edited:
                    sent = await bot.send_message(chat_id, _fmt_comment_text(c["date"], c["text"]))
                    await update_comment(c["id"], {"tg_state": "done", "tg_message_id": sent.message_id})
            elif state_ == "delete":
                if c.get("tg_message_id"):
                    try:
                        await bot.delete_message(chat_id, c["tg_message_id"])
                    except Exception:
                        pass
                await hard_delete_comment(c["id"])
        except Exception as e:
            logging.warning("Комментарий %s: %s", c["id"], e)
            if state_ != "delete":
                await update_comment(c["id"], {"tg_state": "done"})


async def dispatch_loop(bot: Bot, interval: int = 15):
    while True:
        try:
            await _deliver_messages(bot)
            await _cleanup_deleted(bot)
            await _handle_comments(bot)
        except Exception:
            logging.exception("Ошибка в цикле доставки")
        await asyncio.sleep(interval)
