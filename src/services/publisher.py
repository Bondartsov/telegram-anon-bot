"""
M-PUBLISHER: Topic Publisher Module
====================================
PURPOSE: Publish anonymous questions to group topic
SCOPE: Post messages to topics, delete messages
DEPENDS: M-ANONYMIZER
"""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.services.anonymizer import AnonContent

logger = logging.getLogger("anon_bot")


def format_anonymous_message(content: AnonContent) -> str:
    return f"\U0001f512 <b>\u0410\u043d\u043e\u043d\u0438\u043c\u043d\u044b\u0439 \u0432\u043e\u043f\u0440\u043e\u0441</b>\n\n{content.text}"


async def publish_question(
    bot: Bot,
    content: AnonContent,
    group_id: Optional[int] = None,
    topic_id: Optional[int] = None
) -> int:
    """
    Publish anonymous question to group topic.

    Returns:
        int: Message ID of posted question
    """
    if topic_id is None:
        raise ValueError("TOPIC_NOT_CONFIGURED: No topic ID provided")

    formatted_text = format_anonymous_message(content)

    try:
        if content.is_photo:
            message = await bot.send_photo(
                chat_id=group_id, photo=content.media_file_id,
                caption=formatted_text, parse_mode="HTML", message_thread_id=topic_id
            )
            logger.info(f"[M-PUBLISHER][publish_question][PHOTO] Posted to group {group_id}, topic {topic_id}")
        else:
            message = await bot.send_message(
                chat_id=group_id, text=formatted_text,
                parse_mode="HTML", message_thread_id=topic_id
            )
            logger.info(f"[M-PUBLISHER][publish_question][TEXT] Posted text question to group {group_id}, topic {topic_id}")
        return message.message_id

    except TelegramBadRequest as e:
        logger.error(f"[M-PUBLISHER][publish_question][BAD_REQUEST] {e}")
        raise ValueError(f"POST_FAILED: {e}")

    except TelegramForbiddenError as e:
        logger.error(f"[M-PUBLISHER][publish_question][FORBIDDEN] Bot not in group or not admin: {e}")
        raise ValueError("BOT_NOT_ADMIN: Bot is not a member or admin of this group")


async def delete_from_topic(bot: Bot, group_id: int, topic_id: int, message_id: int) -> bool:
    """Delete a message from group topic."""
    try:
        await bot.delete_message(chat_id=group_id, message_id=message_id)
        logger.info(f"[M-PUBLISHER][delete_from_topic][DELETE] Deleted message {message_id} from group {group_id}")
        return True
    except TelegramBadRequest as e:
        if "message to delete not found" in str(e).lower():
            return False
        raise ValueError(f"DELETE_FAILED: {e}")
    except TelegramForbiddenError as e:
        raise ValueError("NO_PERMISSION: Bot cannot delete this message")
