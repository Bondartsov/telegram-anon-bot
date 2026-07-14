"""
M-MEMBERSHIP: Membership Checker Module
=======================================
PURPOSE: Verify user membership in target group
SCOPE: Telegram API calls for membership verification
DEPENDS: none
"""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

logger = logging.getLogger("anon_bot")


async def is_group_member(bot: Bot, user_id: int, group_id: int) -> bool:
    """
    Check if user is a member of the target group.

    Valid statuses: member, administrator, creator, restricted
    Invalid statuses: left, kicked

    Returns:
        bool: True if user is a member, False otherwise
    """
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        valid_statuses = {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.RESTRICTED
        }
        is_member = member.status in valid_statuses
        logger.info(f"[M-MEMBERSHIP][is_group_member][RESULT] User {user_id}: status={member.status}, is_member={is_member}")
        return is_member
    except Exception as e:
        logger.error(f"[M-MEMBERSHIP][is_group_member][ERROR] User {user_id} in group {group_id}: {e}")
        return False


async def is_admin(bot: Bot, user_id: int, group_id: int) -> bool:
    """
    Check if user is an admin or creator of the group.

    Returns:
        bool: True if user is admin or creator
    """
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception as e:
        logger.error(f"[M-MEMBERSHIP][is_admin][ERROR] User {user_id} in group {group_id}: {e}")
        return False
