"""
M-HANDLER-CALLBACK: Callback Handler
=====================================
PURPOSE: Handle inline button callbacks for moderation and deletion
SCOPE: Question approval, rejection, deletion
DEPENDS: M-PUBLISHER, M-DB, M-CONFIG
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.database import (
    delete_question as db_delete_question,
    get_user_questions,
    get_question_by_id,
    approve_question,
    reject_question,
    get_user_id_by_question
)
from src.services.publisher import delete_from_topic, publish_question
from src.services.anonymizer import AnonContent
from src.config import config

logger = logging.getLogger("anon_bot")
router = Router()


async def show_delete_keyboard(bot: Bot, db, user_id: int, chat_id: int) -> None:
    """Show inline keyboard with user's recent questions for deletion."""
    questions = await get_user_questions(db, user_id, limit=5, hours=24)
    if not questions:
        await bot.send_message(
            chat_id=chat_id,
            text="\U0001f4ed <b>\u0423 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432 \u0434\u043b\u044f \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f</b>",
            parse_mode="HTML"
        )
        return
    buttons = [[
        InlineKeyboardButton(text=f"\u274c {i}. {q['content']}", callback_data=f"del_select:{q['id']}")
    ] for i, q in enumerate(questions, 1)]
    await bot.send_message(
        chat_id=chat_id,
        text="\U0001f5d1 <b>\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441 \u0434\u043b\u044f \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("del_select:"))
async def cb_delete_select(callback: CallbackQuery, bot: Bot, db) -> None:
    question_id = callback.data.split(":")[1]
    questions = await get_user_questions(db, callback.from_user.id, limit=5, hours=24)
    selected = next((q for q in questions if q["id"] == question_id), None)
    if not selected:
        await callback.answer("\u274c \u0412\u043e\u043f\u0440\u043e\u0441 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d", show_alert=True)
        await callback.message.delete()
        return
    content = selected["full_content"][:197] + "..." if len(selected["full_content"]) > 200 else selected["full_content"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="\u2705 \u0414\u0430, \u0443\u0434\u0430\u043b\u0438\u0442\u044c", callback_data=f"del_confirm:{question_id}"),
        InlineKeyboardButton(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data="del_cancel")
    ]])
    await callback.message.edit_text(
        f"\u26a0\ufe0f <b>\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435 \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f</b>\n\n{content}",
        parse_mode="HTML", reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery, bot: Bot, db) -> None:
    question_id = callback.data.split(":")[1]
    result = await db_delete_question(db, question_id, callback.from_user.id)
    if not result:
        await callback.answer("\u274c \u0412\u043e\u043f\u0440\u043e\u0441 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d", show_alert=True)
        return
    try:
        await delete_from_topic(bot=bot, group_id=result["group_id"], topic_id=result["topic_id"], message_id=result["topic_message_id"])
        await callback.message.edit_text("\u2705 <b>\u0412\u043e\u043f\u0440\u043e\u0441 \u0443\u0434\u0430\u043b\u0451\u043d!</b>", parse_mode="HTML")
    except ValueError as e:
        await callback.answer(f"\u274c {e}", show_alert=True)


@router.callback_query(F.data == "del_cancel")
async def cb_delete_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("\u274c <b>\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u043e</b>", parse_mode="HTML")


@router.callback_query(F.data.startswith("mod_approve:"))
async def cb_mod_approve(callback: CallbackQuery, bot: Bot, db) -> None:
    """Admin approves a question — publish to group topic."""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("\u274c \u0422\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440", show_alert=True)
        return
    question_id = callback.data.split(":")[1]
    question = await get_question_by_id(db, question_id)
    if not question:
        await callback.answer("\u274c \u0412\u043e\u043f\u0440\u043e\u0441 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d", show_alert=True)
        return
    if question["status"] != "pending":
        await callback.answer("\u26a0\ufe0f \u0423\u0436\u0435 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d", show_alert=True)
        return
    try:
        content = AnonContent(text=question["content"], media_type=question["media_type"], media_file_id=question["media_file_id"])
        message_id = await publish_question(bot=bot, content=content, group_id=question["group_id"], topic_id=question["topic_id"])
        await approve_question(db, question_id, message_id)
        try:
            await bot.send_message(chat_id=question["user_id"], text="\u2705 \u0412\u0430\u0448 \u0432\u043e\u043f\u0440\u043e\u0441 \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d!")
        except Exception:
            pass
        try:
            current_text = callback.message.text or callback.message.caption or ""
            new_text = current_text + "\n\n\u2705 <b>\u2014 \u041e\u0414\u041e\u0411\u0420\u0415\u041d\u041e</b>"
            if callback.message.photo:
                await callback.message.edit_caption(caption=new_text, parse_mode="HTML", reply_markup=None)
            else:
                await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
        logger.info(f"[M-HANDLER-CALLBACK][cb_mod_approve][APPROVE] Question {question_id} approved and published")
    except Exception as e:
        logger.error(f"[M-HANDLER-CALLBACK][cb_mod_approve][ERROR] {e}")
        try:
            await callback.answer("\u274c \u041e\u0448\u0438\u0431\u043a\u0430", show_alert=True)
        except Exception:
            pass


@router.callback_query(F.data.startswith("mod_reject:"))
async def cb_mod_reject(callback: CallbackQuery, bot: Bot, db) -> None:
    """Admin rejects a question."""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("\u274c \u0422\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440", show_alert=True)
        return
    question_id = callback.data.split(":")[1]
    rejected = await reject_question(db, question_id)
    if not rejected:
        await callback.answer("\u26a0\ufe0f \u0423\u0436\u0435 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d", show_alert=True)
        return
    user_id = await get_user_id_by_question(db, question_id)
    if user_id:
        try:
            await bot.send_message(chat_id=user_id, text="\u274c \u0412\u0430\u0448 \u0432\u043e\u043f\u0440\u043e\u0441 \u043e\u0442\u043a\u043b\u043e\u043d\u0451\u043d \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440\u043e\u043c.")
        except Exception:
            pass
    try:
        current_text = callback.message.text or callback.message.caption or ""
        new_text = current_text + "\n\n\u274c <b>\u2014 \u041e\u0422\u041a\u041b\u041e\u041d\u0415\u041d\u041e</b>"
        if callback.message.photo:
            await callback.message.edit_caption(caption=new_text, parse_mode="HTML", reply_markup=None)
        else:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
    except Exception:
        pass
    logger.info(f"[M-HANDLER-CALLBACK][cb_mod_reject][REJECT] Question {question_id} rejected")
