"""
M-HANDLER-CALLBACK: Callback Handler
=====================================
PURPOSE: Handle inline button callbacks for deletion
SCOPE: Question deletion confirmation/cancellation
DEPENDS: M-PUBLISHER, M-DB
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

# Create router for callback handlers
router = Router()


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Callback Handler

PURPOSE:
    Handle inline button callbacks for question deletion.

INPUTS:
    - callback: CallbackQuery — Inline button callback

OUTPUTS:
    - response: Message | bool — Updated message or confirmation

ERRORS:
    - INVALID_QUESTION: Question not found or already deleted
    - NOT_OWNER: User did not create this question

EXPORTS:
    - router: Aiogram router with registered handlers
    - show_delete_keyboard: Helper to show deletion keyboard
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. show_delete_keyboard — Show keyboard with user's questions
    2. cb_delete_select — Handle question selection for deletion
    3. cb_delete_confirm — Confirm and execute deletion
    4. cb_delete_cancel — Cancel deletion dialog
"""

# ==============================================================================
# START_BLOCK: show_delete_keyboard
# ==============================================================================

async def show_delete_keyboard(
    bot: Bot,
    db,
    user_id: int,
    chat_id: int
) -> None:
    """
    Show inline keyboard with user's recent questions.
    
    Args:
        bot: Aiogram Bot instance
        db: Database connection
        user_id: Telegram user ID
        chat_id: Chat ID to send keyboard to
    """
    # Get user's recent questions
    questions = await get_user_questions(db, user_id, limit=5, hours=24)
    
    if not questions:
        await bot.send_message(
            chat_id=chat_id,
            text="📭 <b>У вас нет вопросов для удаления</b>\n\n"
                 "Вы не задавали вопросов за последние 24 часа.",
            parse_mode="HTML"
        )
        return
    
    # Build inline keyboard
    buttons = []
    for i, q in enumerate(questions, 1):
        # Truncate content for button
        content = q["content"]
        if len(content) > 30:
            content = content[:27] + "..."
        
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {i}. {content}",
                callback_data=f"del_select:{q['id']}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await bot.send_message(
        chat_id=chat_id,
        text="🗑 <b>Выберите вопрос для удаления:</b>\n\n"
             "Нажмите на вопрос, который хотите удалить.",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    logger.info(
        f"[M-HANDLER-CALLBACK][show_delete_keyboard][SHOW] "
        f"Showing {len(questions)} questions for user {user_id}"
    )

# ==============================================================================
# END_BLOCK: show_delete_keyboard
# ==============================================================================


# ==============================================================================
# START_BLOCK: cb_delete_select
# ==============================================================================

@router.callback_query(F.data.startswith("del_select:"))
async def cb_delete_select(callback: CallbackQuery, bot: Bot, db) -> None:
    """
    Handle question selection for deletion.
    
    Shows confirmation dialog with the selected question.
    """
    user_id = callback.from_user.id
    question_id = callback.data.split(":")[1]
    
    # Get user's questions to find the selected one
    questions = await get_user_questions(db, user_id, limit=5, hours=24)
    selected = next((q for q in questions if q["id"] == question_id), None)
    
    if not selected:
        await callback.answer("❌ Вопрос не найден или уже удалён", show_alert=True)
        await callback.message.delete()
        return
    
    # Show confirmation dialog
    content = selected["full_content"]
    if len(content) > 200:
        content = content[:197] + "..."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=f"del_confirm:{question_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="del_cancel"
            )
        ]
    ])
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"<b>Вопрос:</b>\n{content}\n\n"
        f"Вы уверены, что хотите удалить этот вопрос?",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    logger.info(
        f"[M-HANDLER-CALLBACK][cb_delete_select][SELECT] "
        f"User {user_id} selected question {question_id} for deletion"
    )

# ==============================================================================
# END_BLOCK: cb_delete_select
# ==============================================================================


# ==============================================================================
# START_BLOCK: cb_delete_confirm
# ==============================================================================

@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery, bot: Bot, db) -> None:
    """
    Handle deletion confirmation.
    
    Deletes the question from topic and marks as deleted in database.
    """
    user_id = callback.from_user.id
    question_id = callback.data.split(":")[1]
    
    # Delete from database and get topic info
    result = await db_delete_question(db, question_id, user_id)
    
    if not result:
        await callback.answer("❌ Вопрос не найден или уже удалён", show_alert=True)
        await callback.message.delete()
        return
    
    # Delete from topic
    try:
        deleted = await delete_from_topic(
            bot=bot,
            group_id=result["group_id"],
            topic_id=result["topic_id"],
            message_id=result["topic_message_id"]
        )
        
        if deleted:
            await callback.message.edit_text(
                "✅ <b>Вопрос удалён!</b>\n\n"
                "Вопрос успешно удалён из группы.",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "⚠️ <b>Вопрос помечен как удалён</b>\n\n"
                "Сообщение в группе уже было удалено ранее.",
                parse_mode="HTML"
            )
        
        logger.info(
            f"[M-HANDLER-CALLBACK][cb_delete_confirm][DELETED] "
            f"Question {question_id} deleted by user {user_id}"
        )
        
    except ValueError as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
        await callback.message.delete()
        logger.error(
            f"[M-HANDLER-CALLBACK][cb_delete_confirm][ERROR] "
            f"Failed to delete question {question_id}: {e}"
        )

# ==============================================================================
# END_BLOCK: cb_delete_confirm
# ==============================================================================


# ==============================================================================
# START_BLOCK: cb_delete_cancel
# ==============================================================================

@router.callback_query(F.data == "del_cancel")
async def cb_delete_cancel(callback: CallbackQuery) -> None:
    """
    Handle deletion cancellation.
    
    Removes the deletion dialog.
    """
    await callback.message.edit_text(
        "❌ <b>Удаление отменено</b>\n\n"
        "Вопрос не был удалён.",
        parse_mode="HTML"
    )
    
    logger.info(
        f"[M-HANDLER-CALLBACK][cb_delete_cancel][CANCEL] "
        f"User {callback.from_user.id} cancelled deletion"
    )

# ==============================================================================
# END_BLOCK: cb_delete_cancel
# ==============================================================================


# ==============================================================================
# START_BLOCK: cb_mod_approve
# ==============================================================================

@router.callback_query(F.data.startswith("mod_approve:"))
async def cb_mod_approve(callback: CallbackQuery, bot: Bot, db) -> None:
    """
    Handle question approval by admin.
    
    Publishes the question to the group topic and notifies the user.
    """
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("❌ Только администратор может модерировать вопросы", show_alert=True)
        return
    
    question_id = callback.data.split(":")[1]
    
    question = await get_question_by_id(db, question_id)
    
    if not question:
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        await callback.message.delete()
        return
    
    if question["status"] != "pending":
        await callback.answer("⚠️ Вопрос уже обработан", show_alert=True)
        await callback.message.delete()
        return
    
    try:
        content = AnonContent(
            text=question["content"],
            media_type=question["media_type"],
            media_file_id=question["media_file_id"]
        )
        
        message_id = await publish_question(
            bot=bot,
            content=content,
            group_id=question["group_id"],
            topic_id=question["topic_id"]
        )
        
        await approve_question(db, question_id, message_id)
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=question["user_id"],
                text="✅ Ваш вопрос опубликован!"
            )
        except Exception:
            pass
        
        # Убираем кнопки, добавляем статус к сообщению админа
        try:
            current_text = callback.message.text or callback.message.caption or ""
            new_text = current_text + "\n\n✅ <b>— ОДОБРЕНО</b>"
            
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=new_text,
                    parse_mode="HTML",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    new_text,
                    parse_mode="HTML",
                    reply_markup=None
                )
        except Exception:
            pass
        
        logger.info(
            f"[M-HANDLER-CALLBACK][cb_mod_approve][APPROVE] "
            f"Question {question_id} approved and published"
        )
        
    except Exception as e:
        logger.error(f"[M-HANDLER-CALLBACK][cb_mod_approve][ERROR] {e}")
        try:
            await callback.answer("❌ Ошибка", show_alert=True)
        except Exception:
            pass

# ==============================================================================
# END_BLOCK: cb_mod_approve
# ==============================================================================


# ==============================================================================
# START_BLOCK: cb_mod_reject
# ==============================================================================

@router.callback_query(F.data.startswith("mod_reject:"))
async def cb_mod_reject(callback: CallbackQuery, bot: Bot, db) -> None:
    """
    Handle question rejection by admin.
    
    Marks question as rejected and notifies the user.
    """
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("❌ Только администратор может модерировать вопросы", show_alert=True)
        return
    
    question_id = callback.data.split(":")[1]
    
    rejected = await reject_question(db, question_id)
    
    if not rejected:
        try:
            await callback.answer("⚠️ Вопрос уже обработан", show_alert=True)
        except Exception:
            pass
        return
    
    user_id = await get_user_id_by_question(db, question_id)
    
    # Уведомляем пользователя
    if user_id:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Извините, ваш вопрос был отклонён модератором."
            )
        except Exception:
            pass
    
    # Убираем кнопки, добавляем статус к сообщению админа
    try:
        current_text = callback.message.text or callback.message.caption or ""
        new_text = current_text + "\n\n❌ <b>— ОТКЛОНЕНО</b>"
        
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=new_text,
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                new_text,
                parse_mode="HTML",
                reply_markup=None
            )
    except Exception:
        pass
    
    logger.info(
        f"[M-HANDLER-CALLBACK][cb_mod_reject][REJECT] "
        f"Question {question_id} rejected"
    )

# ==============================================================================
# END_BLOCK: cb_mod_reject
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Implemented show_delete_keyboard helper
    - Implemented cb_delete_select for question selection
    - Implemented cb_delete_confirm for actual deletion
    - Implemented cb_delete_cancel for cancellation
    - Proper error handling and user feedback
    - Logging for all operations
"""

