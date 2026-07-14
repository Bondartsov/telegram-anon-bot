"""
M-PUBLISHER: Topic Publisher Module
====================================
PURPOSE: Publish anonymous questions to group topic
SCOPE: Post messages to topics, delete messages
DEPENDS: M-CONFIG, M-DB, M-ANONYMIZER
"""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.config import config
from src.services.anonymizer import AnonContent

logger = logging.getLogger("anon_bot")


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Topic Publisher Module

PURPOSE:
    Publish anonymous questions to configured group topics.

INPUTS:
    - bot: Bot — Aiogram Bot instance
    - content: AnonContent — Content to publish
    - group_id: int — Target group ID
    - topic_id: int — Target topic ID

OUTPUTS:
    - message_id: int — ID of posted message

ERRORS:
    - POST_FAILED: Failed to post message
    - TOPIC_NOT_FOUND: Topic does not exist
    - BOT_NOT_ADMIN: Bot is not admin in group

EXPORTS:
    - publish_question: Post question to topic
    - delete_from_topic: Remove question from topic
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. publish_question — Post anonymous question to topic
    2. delete_from_topic — Delete message from topic
    3. format_anonymous_message — Format message with disclaimer
"""

# ==============================================================================
# START_BLOCK: format_anonymous_message
# ==============================================================================

def format_anonymous_message(content: AnonContent) -> str:
    """
    Format anonymous message.
    
    Args:
        content: Anonymized content
        
    Returns:
        str: Formatted message text
    """
    return f"🔒 <b>Анонимный вопрос</b>\n\n{content.text}"

# ==============================================================================
# END_BLOCK: format_anonymous_message
# ==============================================================================


# ==============================================================================
# START_BLOCK: publish_question
# ==============================================================================

async def publish_question(
    bot: Bot,
    content: AnonContent,
    group_id: Optional[int] = None,
    topic_id: Optional[int] = None
) -> int:
    """
    Publish anonymous question to group topic.
    
    Args:
        bot: Aiogram Bot instance
        content: Anonymized content to publish
        group_id: Target group ID (uses config if not provided)
        topic_id: Target topic ID (uses config if not provided)
        
    Returns:
        int: Message ID of posted question
        
    Raises:
        ValueError: If topic not configured or content invalid
        TelegramBadRequest: If posting fails
    """
    if group_id is None:
        group_id = config.GROUP_ID
    if topic_id is None:
        raise ValueError("TOPIC_NOT_CONFIGURED: No topic ID provided or configured")
    
    try:
        # Format message text
        formatted_text = format_anonymous_message(content)
        
        # Post based on content type
        if content.is_photo:
            # Post photo with caption
            message = await bot.send_photo(
                chat_id=group_id,
                photo=content.media_file_id,
                caption=formatted_text,
                parse_mode="HTML",
                message_thread_id=topic_id
            )
            logger.info(
                f"[M-PUBLISHER][publish_question][PHOTO] "
                f"Posted photo question to group {group_id}, topic {topic_id}"
            )
        else:
            # Post text only
            message = await bot.send_message(
                chat_id=group_id,
                text=formatted_text,
                parse_mode="HTML",
                message_thread_id=topic_id
            )
            logger.info(
                f"[M-PUBLISHER][publish_question][TEXT] "
                f"Posted text question to group {group_id}, topic {topic_id}"
            )
        
        return message.message_id
        
    except TelegramBadRequest as e:
        logger.error(
            f"[M-PUBLISHER][publish_question][BAD_REQUEST] "
            f"Failed to post: {e}"
        )
        raise ValueError(f"POST_FAILED: {e}")
        
    except TelegramForbiddenError as e:
        logger.error(
            f"[M-PUBLISHER][publish_question][FORBIDDEN] "
            f"Bot not in group or not admin: {e}"
        )
        raise ValueError("BOT_NOT_ADMIN: Bot is not a member or admin of this group")

# ==============================================================================
# END_BLOCK: publish_question
# ==============================================================================


# ==============================================================================
# START_BLOCK: delete_from_topic
# ==============================================================================

async def delete_from_topic(
    bot: Bot,
    group_id: int,
    topic_id: int,
    message_id: int
) -> bool:
    """
    Delete a message from group topic.
    
    Args:
        bot: Aiogram Bot instance
        group_id: Group ID
        topic_id: Topic ID
        message_id: Message ID to delete
        
    Returns:
        bool: True if deleted successfully
        
    Raises:
        ValueError: If deletion fails
    """
    try:
        await bot.delete_message(
            chat_id=group_id,
            message_id=message_id
        )
        
        logger.info(
            f"[M-PUBLISHER][delete_from_topic][DELETE] "
            f"Deleted message {message_id} from group {group_id}"
        )
        
        return True
        
    except TelegramBadRequest as e:
        # Message might already be deleted
        if "message to delete not found" in str(e).lower():
            logger.warning(
                f"[M-PUBLISHER][delete_from_topic][NOT_FOUND] "
                f"Message {message_id} already deleted"
            )
            return False
        raise ValueError(f"DELETE_FAILED: {e}")
        
    except TelegramForbiddenError as e:
        logger.error(
            f"[M-PUBLISHER][delete_from_topic][FORBIDDEN] "
            f"No permission to delete: {e}"
        )
        raise ValueError("NO_PERMISSION: Bot cannot delete this message")

# ==============================================================================
# END_BLOCK: delete_from_topic
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Implemented publish_question for text and photo content
    - Added format_anonymous_message with disclaimer
    - Implemented delete_from_topic for question removal
    - Proper error handling for Telegram API errors
    - Logging for all operations
"""

