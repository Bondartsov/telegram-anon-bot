"""
M-HANDLER-GROUP: Group Event Handler
=====================================
PURPOSE: Handle group events and admin commands
SCOPE: /set_topic, /settings, /start in group
DEPENDS: M-DB, M-CONFIG, M-MEMBERSHIP
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import config
from src.database import get_group_config, set_group_config
from src.services.membership import is_admin

logger = logging.getLogger("anon_bot")
router = Router()


def get_bot_info_text(bot_username: str) -> str:
    return (
        f"\n\n"
        f"\U0001f4dd <b>\u041a\u0430\u043a \u0437\u0430\u0434\u0430\u0442\u044c \u0432\u043e\u043f\u0440\u043e\u0441:</b>\n"
        f"\u2022 \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0442\u0435\u043a\u0441\u0442 \u0432\u043e\u043f\u0440\u043e\u0441\u0430\n"
        f"\u2022 \u0418\u043b\u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0444\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u043f\u0438\u0441\u044c\u044e\n\n"
        f"\U0001f4e8 <b>\u041f\u0438\u0448\u0438\u0442\u0435 \u0431\u043e\u0442\u0443:</b> @{bot_username}"
    )


@router.message(Command("set_topic"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_set_topic(message: Message, bot: Bot, db) -> None:
    """
    Set the current topic as target for anonymous questions.
    Only group admins can use this command.
    Must be sent inside a topic (thread).
    """
    user = message.from_user
    chat = message.chat

    if not message.message_thread_id:
        await message.reply(
            "\u26a0\ufe0f <b>\u042d\u0442\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0434\u043e\u043b\u0436\u043d\u0430 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c\u0441\u044f \u0432\u043d\u0443\u0442\u0440\u0438 \u0442\u0435\u043c\u044b!</b>\n\n"
            "\u041f\u0435\u0440\u0435\u0439\u0434\u0438\u0442\u0435 \u0432 \u043d\u0443\u0436\u043d\u0443\u044e \u0442\u0435\u043c\u0443 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 /set_topic \u0442\u0430\u043c.",
            parse_mode="HTML"
        )
        return

    if not await is_admin(bot, user.id, chat.id):
        await message.reply(
            "\u274c <b>\u0422\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u044b \u043c\u043e\u0433\u0443\u0442 \u043d\u0430\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0442\u044c \u0431\u043e\u0442\u0430!</b>",
            parse_mode="HTML"
        )
        return

    topic_id = message.message_thread_id
    await set_group_config(db, group_id=chat.id, topic_id=topic_id)
    me = await bot.get_me()

    await message.reply(
        f"\u2705 <b>\u0422\u0435\u043c\u0430 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0430!</b>\n"
        f"\u0410\u043d\u043e\u043d\u0438\u043c\u043d\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u0431\u0443\u0434\u0443\u0442 \u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u0442\u044c\u0441\u044f \u0441\u044e\u0434\u0430.{get_bot_info_text(me.username)}",
        parse_mode="HTML"
    )
    logger.info(f"[M-HANDLER-GROUP][cmd_set_topic][SET] Group {chat.id} topic set to {topic_id} by user {user.id}")


@router.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_settings(message: Message, bot: Bot, db) -> None:
    """Show current bot configuration for this group."""
    chat = message.chat
    me = await bot.get_me()
    topic_id = await get_group_config(db, chat.id)

    if topic_id:
        text = (
            f"\u2699\ufe0f <b>\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0431\u043e\u0442\u0430</b>\n\n"
            f"<b>\u0413\u0440\u0443\u043f\u043f\u0430:</b> {chat.title}\n"
            f"<b>\u0422\u0435\u043c\u0430:</b> \u2705 \u041d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0430\n"
            f"<b>\u041b\u0438\u043c\u0438\u0442:</b> {config.RATE_LIMIT}/\u0447\u0430\u0441\n\n"
            f"\u2705 \u0411\u043e\u0442 \u0433\u043e\u0442\u043e\u0432 \u043a \u0440\u0430\u0431\u043e\u0442\u0435!"
            f"{get_bot_info_text(me.username)}\n\n"
            f"\U0001f4a1 <i>\u0427\u0442\u043e\u0431\u044b \u0441\u043c\u0435\u043d\u0438\u0442\u044c \u0442\u0435\u043c\u0443 \u2014 \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 /set_topic \u0432 \u043d\u0443\u0436\u043d\u043e\u0439 \u0442\u0435\u043c\u0435</i>"
        )
    else:
        text = (
            f"\u2699\ufe0f <b>\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0431\u043e\u0442\u0430</b>\n\n"
            f"<b>\u0413\u0440\u0443\u043f\u043f\u0430:</b> {chat.title}\n"
            f"<b>\u0422\u0435\u043c\u0430:</b> \u274c \u041d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0430\n\n"
            f"\u26a0\ufe0f \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 /set_topic \u0432 \u043d\u0443\u0436\u043d\u043e\u0439 \u0442\u0435\u043c\u0435."
            f"{get_bot_info_text(me.username)}"
        )

    await message.reply(text, parse_mode="HTML")


@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_start_group(message: Message, bot: Bot) -> None:
    """Show bot info in group."""
    me = await bot.get_me()
    await message.reply(
        f"\U0001f916 <b>\u0411\u043e\u0442 \u0430\u043d\u043e\u043d\u0438\u043c\u043d\u044b\u0445 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432</b>\n\n"
        f"<b>\u0414\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432:</b>\n"
        f"/set_topic \u2014 \u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u0442\u0435\u043c\u0443 \u0434\u043b\u044f \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432\n"
        f"/settings \u2014 \u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438"
        f"{get_bot_info_text(me.username)}",
        parse_mode="HTML"
    )
