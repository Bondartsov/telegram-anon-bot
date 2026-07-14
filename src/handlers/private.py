"""
M-HANDLER-PRIVATE: Private Chat Handler
========================================
PURPOSE: Handle messages in private chats
SCOPE: /start, /delete, /mod_history, /stats, question submission
DEPENDS: M-CONFIG, M-DB, M-ANONYMIZER, M-RATE-LIMIT, M-HANDLER-CALLBACK
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import config
from src.database import (
    get_latest_group_config, 
    save_pending_question,
    get_moderation_history,
    get_stats
)
from src.handlers.callback import show_delete_keyboard
from src.services.anonymizer import prepare_content, validate_content
from src.services.membership import is_group_member
from src.services.rate_limiter import get_rate_limiter

logger = logging.getLogger("anon_bot")

router = Router()


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Private Chat Handler

PURPOSE:
    Handle all private chat messages for the anonymous questions bot.

INPUTS:
    - message: Message — Private chat message from user

OUTPUTS:
    - response: Message — Feedback to user

ERRORS:
    - RATE_EXCEEDED: User exceeded hourly rate limit
    - TOPIC_NOT_CONFIGURED: No topic configured for group
    - INVALID_CONTENT: Content validation failed

EXPORTS:
    - router: Aiogram router with registered handlers
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. cmd_start — Welcome message and instructions
    2. cmd_delete — Show deletion keyboard
    3. handle_question — Process text/photo questions with moderation
"""

# ==============================================================================
# START_BLOCK: cmd_start
# ==============================================================================

@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message) -> None:
    """
    Handle /start command in private chat.
    
    Shows welcome message with instructions.
    """
    welcome_text = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Я бот для анонимных вопросов.\n\n"
        
        "📝 <b>Как задать вопрос:</b>\n"
        "• Напишите текст вопроса\n"
        "• Или отправьте фото с подписью\n\n"
        
        "🔒 <b>Анонимность гарантирована:</b>\n"
        "• Админ видит только текст вопроса\n"
        "• Ваша личность скрыта полностью\n"
        "• Вопрос публикуется без имени\n\n"
        
        "✅ <b>Лёгкая модерация:</b>\n"
        "• Вопросы проверяются на адекватность\n"
        "• Глупости и спам не пройдут\n\n"
        
        f"⏱ <b>Лимит:</b> {config.RATE_LIMIT} вопросов/час\n\n"
        
        "🗑 <b>Команды:</b>\n"
        "• /delete — удалить ваш вопрос"
    )
    
    await message.answer(welcome_text, parse_mode="HTML")
    
    logger.info(
        f"[M-HANDLER-PRIVATE][cmd_start][WELCOME] "
        f"User {message.from_user.id} started the bot"
    )

# ==============================================================================
# END_BLOCK: cmd_start
# ==============================================================================


# ==============================================================================
# START_BLOCK: cmd_delete
# ==============================================================================

@router.message(Command("delete"), F.chat.type == "private")
async def cmd_delete(message: Message, bot: Bot, db) -> None:
    """
    Handle /delete command in private chat.
    
    Shows keyboard with user's questions for deletion.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await show_delete_keyboard(bot, db, user_id, chat_id)
    
    logger.info(
        f"[M-HANDLER-PRIVATE][cmd_delete][REQUEST] "
        f"User {user_id} requested delete keyboard"
    )

# ==============================================================================
# END_BLOCK: cmd_delete
# ==============================================================================


# ==============================================================================
# START_BLOCK: Admin commands
# ==============================================================================

@router.message(Command("mod_history"), F.chat.type == "private")
async def cmd_mod_history(message: Message, db) -> None:
    """
    Handle /mod_history command - admin only.
    
    Shows moderation history.
    """
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    history = await get_moderation_history(db, limit=15)
    
    if not history:
        await message.answer("📭 История модерации пуста")
        return
    
    text = "📋 <b>История модерации</b>\n\n"
    
    for item in history:
        status_emoji = "✅" if item["status"] == "approved" else "❌"
        content = item["content"][:80] + "..." if len(item["content"]) > 80 else item["content"]
        text += f"{status_emoji} {content}\n"
        text += f"   └ {item['created_at'][:16]}\n\n"
    
    await message.answer(text, parse_mode="HTML")
    logger.info(f"[M-HANDLER-PRIVATE][cmd_mod_history] Admin viewed history")


@router.message(Command("stats"), F.chat.type == "private")
async def cmd_stats(message: Message, db) -> None:
    """
    Handle /stats command - admin only.
    
    Shows moderation statistics.
    """
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    stats = await get_stats(db)
    
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"📝 Всего вопросов: {stats['total']}\n"
        f"✅ Одобрено: {stats['approved']}\n"
        f"❌ Отклонено: {stats['rejected']}\n"
        f"⏳ Ожидают: {stats['pending']}"
    )
    
    await message.answer(text, parse_mode="HTML")
    logger.info(f"[M-HANDLER-PRIVATE][cmd_stats] Admin viewed stats")

# ==============================================================================
# END_BLOCK: Admin commands
# ==============================================================================

@router.message(F.chat.type == "private")
async def handle_question(message: Message, bot: Bot, db) -> None:
    """
    Handle text or photo messages as question submissions.
    
    Flow:
    1. Check rate limit
    2. Extract and validate content
    3. Get topic configuration
    4. Save as pending question
    5. Send to admin for moderation
    6. Notify user
    """
    user_id = message.from_user.id
    
    # 1. Check rate limit
    rate_limiter = get_rate_limiter()
    limit_check = rate_limiter.check_limit(user_id)
    
    if not limit_check["allowed"]:
        reset_minutes = limit_check["reset_in"] // 60
        await message.answer(
            f"⏱ <b>Превышен лимит вопросов</b>\n\n"
            f"Вы уже отправили {limit_check['current']} вопросов.\n"
            f"Попробуйте через {reset_minutes} минут.",
            parse_mode="HTML"
        )
        logger.info(
            f"[M-HANDLER-PRIVATE][handle_question][RATE_LIMIT] "
            f"User {user_id} exceeded rate limit"
        )
        return
    
    # 2. Extract content
    try:
        content = prepare_content(message)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        logger.warning(
            f"[M-HANDLER-PRIVATE][handle_question][EXTRACT_ERROR] "
            f"User {user_id}: {e}"
        )
        return
    
    # 3. Validate content
    is_valid, error_msg = validate_content(content)
    if not is_valid:
        await message.answer(f"❌ {error_msg}")
        logger.warning(
            f"[M-HANDLER-PRIVATE][handle_question][VALIDATE_ERROR] "
            f"User {user_id}: {error_msg}"
        )
        return
    
    # 4. Get topic configuration
    group_config = await get_latest_group_config(db)
    
    if not group_config:
        await message.answer(
            "❌ <b>Ошибка конфигурации</b>\n\n"
            "Тема для вопросов не настроена. "
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        logger.error(
            f"[M-HANDLER-PRIVATE][handle_question][NO_TOPIC] "
            "No group config found in database"
        )
        return
    

    group_id, topic_id = group_config

    # 4.1 Check group membership
    if not await is_group_member(bot=bot, user_id=user_id, group_id=group_id):
        await message.answer(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "Задавать вопросы могут только участники группы.",
            parse_mode="HTML"
        )
        logger.info(
            f"[M-HANDLER-PRIVATE][handle_question][NOT_MEMBER] "
            f"User {user_id} is not a member of group {group_id}"
        )
        return
    # 5. Save pending question
    question_id = await save_pending_question(
        db=db,
        user_id=user_id,
        content=content.text,
        group_id=group_id,
        topic_id=topic_id,
        media_type=content.media_type,
        media_file_id=content.media_file_id
    )
    
    # 6. Build moderation keyboard for admin
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"mod_approve:{question_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"mod_reject:{question_id}"
            )
        ]
    ])
    
    # 7. Send to admin for moderation
    admin_text = (
        f"🔔 <b>Новый вопрос на модерацию</b>\n\n"
        f"<b>Текст:</b>\n{content.text}"
    )
    
    if content.is_photo:
        await bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=content.media_file_id,
            caption=admin_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    # 8. Notify user
    await message.answer(
        "📨 <b>Вопрос отправлен на модерацию</b>\n\n"
        "После проверки он будет опубликован анонимно.",
        parse_mode="HTML"
    )
    
    # 9. Record submission in rate limiter
    rate_limiter.record_submission(user_id)
    
    logger.info(
        f"[M-HANDLER-PRIVATE][handle_question][SUBMITTED] "
        f"Question {question_id} from user {user_id} sent to moderation"
    )

# ==============================================================================
# END_BLOCK: handle_question
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Implemented cmd_start with welcome message and instructions
    - Implemented cmd_delete delegating to show_delete_keyboard
    - Implemented handle_question with full flow:
      * Rate limit check
      * Content extraction and validation
      * Topic configuration check
      * Pending question save
      * Admin notification with moderation buttons
      * User notification
      * Rate limiter recording
    - All handlers filtered to private chats only
    - Proper error handling and user feedback
    - Logging for all operations
"""

