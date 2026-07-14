"""
M-HANDLER-GROUP: Group Event Handler
=====================================
PURPOSE: Handle group events and admin commands
SCOPE: /set_topic, /settings, bot added to group
DEPENDS: M-DB, M-CONFIG
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import config
from src.database import get_group_config, set_group_config
from src.services.membership import is_admin

logger = logging.getLogger("anon_bot")

# Create router for group handlers
router = Router()


# ==============================================================================
# Helper: Bot info text
# ==============================================================================

def get_bot_info_text(bot_username: str) -> str:
    """Generate bot info text with link."""
    return (
        f"\n\n"
        f"📝 <b>Как задать вопрос:</b>\n"
        f"• Напишите текст вопроса\n"
        f"• Или отправьте фото с подписью\n\n"
        
        f"🔒 <b>Анонимность гарантирована:</b>\n"
        f"• Админ видит только текст вопроса\n"
        f"• Ваша личность скрыта полностью\n"
        f"• Вопрос публикуется без имени\n\n"
        
        f"✅ <b>Лёгкая модерация:</b>\n"
        f"• Вопросы проверяются на адекватность\n"
        f"• Глупости и спам не пройдут\n\n"
        
        f"📨 <b>Пишите боту:</b> @{bot_username}"
    )


# ==============================================================================
# START_BLOCK: cmd_set_topic
# ==============================================================================

@router.message(Command("set_topic"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_set_topic(message: Message, bot: Bot, db) -> None:
    """
    Handle /set_topic command in group.
    
    Sets the current topic (thread) as the target for anonymous questions.
    Only admins can use this command.
    """
    user = message.from_user
    chat = message.chat
    
    # Check if message is in a topic (has message_thread_id)
    if not message.message_thread_id:
        await message.reply(
            "⚠️ <b>Эта команда должна использоваться внутри темы!</b>\n\n"
            "Перейдите в нужную тему и отправьте /set_topic там.",
            parse_mode="HTML"
        )
        return
    
    # Check if user is admin
    if not await is_admin(bot, user.id, chat.id):
        await message.reply(
            "❌ <b>Только администраторы могут настраивать бота!</b>",
            parse_mode="HTML"
        )
        logger.info(
            f"[M-HANDLER-GROUP][cmd_set_topic][NOT_ADMIN] "
            f"User {user.id} tried to set topic without admin rights"
        )
        return
    
    topic_id = message.message_thread_id
    
    # Save configuration
    await set_group_config(db, group_id=chat.id, topic_id=topic_id)
    
    # Get bot username
    me = await bot.get_me()
    
    await message.reply(
        f"✅ <b>Тема настроена!</b>\n"
        f"Анонимные вопросы будут публиковаться сюда.{get_bot_info_text(me.username)}",
        parse_mode="HTML"
    )
    
    logger.info(
        f"[M-HANDLER-GROUP][cmd_set_topic][SET] "
        f"Group {chat.id} topic set to {topic_id} by user {user.id}"
    )

# ==============================================================================
# END_BLOCK: cmd_set_topic
# ==============================================================================


# ==============================================================================
# START_BLOCK: cmd_settings
# ==============================================================================

@router.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_settings(message: Message, bot: Bot, db) -> None:
    """
    Handle /settings command in group.
    
    Shows current bot configuration for the group.
    """
    user = message.from_user
    chat = message.chat
    
    # Get bot username
    me = await bot.get_me()
    
    # Get current configuration
    topic_id = await get_group_config(db, chat.id)
    
    if topic_id:
        settings_text = (
            f"⚙️ <b>Настройки бота</b>\n\n"
            f"<b>Группа:</b> {chat.title}\n"
            f"<b>Тема для вопросов:</b> ✅ Настроена\n"
            f"<b>Лимит вопросов:</b> {config.RATE_LIMIT}/час на пользователя\n\n"
            f"✅ Бот настроен и готов к работе!"
            f"{get_bot_info_text(me.username)}\n\n"
            f"💡 <i>Чтобы сменить тему — напишите /set_topic в нужной теме</i>"
        )
    else:
        settings_text = (
            f"⚙️ <b>Настройки бота</b>\n\n"
            f"<b>Группа:</b> {chat.title}\n"
            f"<b>Тема для вопросов:</b> ❌ Не настроена\n\n"
            f"⚠️ Используйте /set_topic в нужной теме для настройки."
            f"{get_bot_info_text(me.username)}"
        )
    
    await message.reply(settings_text, parse_mode="HTML")
    logger.info(
        f"[M-HANDLER-GROUP][cmd_settings][SHOW] "
        f"User {user.id} viewed settings in group {chat.id}"
    )

# ==============================================================================
# END_BLOCK: cmd_settings
# ==============================================================================


# ==============================================================================
# START_BLOCK: cmd_start_group
# ==============================================================================

@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_start_group(message: Message, bot: Bot) -> None:
    """
    Handle /start command in group.
    
    Shows info message about the bot.
    """
    chat = message.chat
    me = await bot.get_me()
    
    info_text = (
        f"🤖 <b>Бот анонимных вопросов</b>\n\n"
        f"<b>Для администраторов:</b>\n"
        f"/set_topic — Настроить тему для вопросов\n"
        f"/settings — Показать текущие настройки"
        f"{get_bot_info_text(me.username)}"
    )
    
    await message.reply(info_text, parse_mode="HTML")
    logger.info(
        f"[M-HANDLER-GROUP][cmd_start_group][START] "
        f"Bot started in group {chat.id}"
    )

# ==============================================================================
# END_BLOCK: cmd_start_group
# ==============================================================================

