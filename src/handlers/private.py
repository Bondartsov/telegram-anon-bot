"""
M-HANDLER-PRIVATE: Private Chat Handler
========================================
PURPOSE: Handle messages in private chats
SCOPE: /start, /delete, /mod_history, /stats, question submission
DEPENDS: M-CONFIG, M-DB, M-ANONYMIZER, M-RATE-LIMIT, M-MEMBERSHIP
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


@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message) -> None:
    """Welcome message with instructions."""
    welcome_text = (
        "\U0001f44b <b>\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c!</b>\n\n"
        "\u042f \u0431\u043e\u0442 \u0434\u043b\u044f \u0430\u043d\u043e\u043d\u0438\u043c\u043d\u044b\u0445 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432.\n\n"
        "\U0001f4dd <b>\u041a\u0430\u043a \u0437\u0430\u0434\u0430\u0442\u044c \u0432\u043e\u043f\u0440\u043e\u0441:</b>\n"
        "\u2022 \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0442\u0435\u043a\u0441\u0442 \u0432\u043e\u043f\u0440\u043e\u0441\u0430\n"
        "\u2022 \u0418\u043b\u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0444\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u043f\u0438\u0441\u044c\u044e\n\n"
        "\U0001f512 <b>\u0410\u043d\u043e\u043d\u0438\u043c\u043d\u043e\u0441\u0442\u044c \u0433\u0430\u0440\u0430\u043d\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0430</b>\n\n"
        f"\u23f1 <b>\u041b\u0438\u043c\u0438\u0442:</b> {config.RATE_LIMIT} \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432/\u0447\u0430\u0441\n\n"
        "\U0001f5d1 <b>\u041a\u043e\u043c\u0430\u043d\u0434\u044b:</b>\n"
        "\u2022 /delete \u2014 \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u0430\u0448 \u0432\u043e\u043f\u0440\u043e\u0441"
    )
    await message.answer(welcome_text, parse_mode="HTML")
    logger.info(f"[M-HANDLER-PRIVATE][cmd_start][WELCOME] User {message.from_user.id} started the bot")


@router.message(Command("delete"), F.chat.type == "private")
async def cmd_delete(message: Message, bot: Bot, db) -> None:
    """Show deletion keyboard for user's recent questions."""
    await show_delete_keyboard(bot, db, message.from_user.id, message.chat.id)


@router.message(Command("mod_history"), F.chat.type == "private")
async def cmd_mod_history(message: Message, db) -> None:
    """Admin: show moderation history."""
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("\u274c \u042d\u0442\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430")
        return
    history = await get_moderation_history(db, limit=15)
    if not history:
        await message.answer("\U0001f4ed \u0418\u0441\u0442\u043e\u0440\u0438\u044f \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u0438 \u043f\u0443\u0441\u0442\u0430")
        return
    text = "\U0001f4cb <b>\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u0438</b>\n\n"
    for item in history:
        emoji = "\u2705" if item["status"] == "approved" else "\u274c"
        text += f"{emoji} {item['content']}\n   \u2514 {item['created_at'][:16]}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("stats"), F.chat.type == "private")
async def cmd_stats(message: Message, db) -> None:
    """Admin: show bot statistics."""
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("\u274c \u042d\u0442\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430")
        return
    stats = await get_stats(db)
    text = (
        "\U0001f4ca <b>\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 \u0431\u043e\u0442\u0430</b>\n\n"
        f"\U0001f4dd \u0412\u0441\u0435\u0433\u043e: {stats['total']}\n"
        f"\u2705 \u041e\u0434\u043e\u0431\u0440\u0435\u043d\u043e: {stats['approved']}\n"
        f"\u274c \u041e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u043e: {stats['rejected']}\n"
        f"\u23f3 \u041e\u0436\u0438\u0434\u0430\u044e\u0442: {stats['pending']}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.chat.type == "private")
async def handle_question(message: Message, bot: Bot, db) -> None:
    """
    Handle question submissions.

    Flow:
      1. Rate limit check
      2. Extract & validate content
      3. Get active group config from DB (set via /set_topic)
      4. Verify user is a group member
      5. Save pending question
      6. Send to admin for moderation
      7. Notify user
    """
    user_id = message.from_user.id

    # 1. Rate limit
    rate_limiter = get_rate_limiter()
    limit_check = rate_limiter.check_limit(user_id)
    if not limit_check["allowed"]:
        reset_minutes = limit_check["reset_in"] // 60
        await message.answer(
            f"\u23f1 <b>\u041f\u0440\u0435\u0432\u044b\u0448\u0435\u043d \u043b\u0438\u043c\u0438\u0442 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432</b>\n\n"
            f"\u0412\u044b \u0443\u0436\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u043b\u0438 {limit_check['current']} \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432.\n"
            f"\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0447\u0435\u0440\u0435\u0437 {reset_minutes} \u043c\u0438\u043d\u0443\u0442.",
            parse_mode="HTML"
        )
        return

    # 2. Extract & validate
    try:
        content = prepare_content(message)
    except ValueError as e:
        await message.answer(f"\u274c {e}")
        return

    is_valid, error_msg = validate_content(content)
    if not is_valid:
        await message.answer(f"\u274c {error_msg}")
        return

    # 3. Get active group config from DB
    group_config = await get_latest_group_config(db)
    if not group_config:
        await message.answer(
            "\u274c <b>\u041e\u0448\u0438\u0431\u043a\u0430 \u043a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0438</b>\n\n"
            "\u0422\u0435\u043c\u0430 \u0434\u043b\u044f \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0430. "
            "\u041e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043a \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443.",
            parse_mode="HTML"
        )
        return

    group_id, topic_id = group_config

    # 4. Membership check — only group members can submit
    if not await is_group_member(bot=bot, user_id=user_id, group_id=group_id):
        await message.answer(
            "\U0001f512 <b>\u0414\u043e\u0441\u0442\u0443\u043f \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d</b>\n\n"
            "\u0417\u0430\u0434\u0430\u0432\u0430\u0442\u044c \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043c\u043e\u0433\u0443\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0438 \u0433\u0440\u0443\u043f\u043f\u044b.",
            parse_mode="HTML"
        )
        logger.info(f"[M-HANDLER-PRIVATE][handle_question][NOT_MEMBER] User {user_id} is not a member of group {group_id}")
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
    rate_limiter.record_submission(user_id)
    logger.info(f"[M-HANDLER-PRIVATE][handle_question][SUBMITTED] Question {question_id} from user {user_id} sent to moderation")

    # 6. Send to admin for moderation
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="\u2705 \u041e\u0434\u043e\u0431\u0440\u0438\u0442\u044c", callback_data=f"mod_approve:{question_id}"),
        InlineKeyboardButton(text="\u274c \u041e\u0442\u043a\u043b\u043e\u043d\u0438\u0442\u044c", callback_data=f"mod_reject:{question_id}")
    ]])
    admin_text = f"\U0001f514 <b>\u041d\u043e\u0432\u044b\u0439 \u0432\u043e\u043f\u0440\u043e\u0441 \u043d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u044e</b>\n\n<b>\u0422\u0435\u043a\u0441\u0442:</b>\n{content.text}"
    if content.is_photo:
        await bot.send_photo(chat_id=config.ADMIN_ID, photo=content.media_file_id, caption=admin_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=config.ADMIN_ID, text=admin_text, parse_mode="HTML", reply_markup=keyboard)

    # 7. Notify user
    await message.answer(
        "\U0001f4e8 <b>\u0412\u043e\u043f\u0440\u043e\u0441 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d \u043d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u044e</b>\n\n"
        "\u041f\u043e\u0441\u043b\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u043e\u043d \u0431\u0443\u0434\u0435\u0442 \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d \u0430\u043d\u043e\u043d\u0438\u043c\u043d\u043e.",
        parse_mode="HTML"
    )
