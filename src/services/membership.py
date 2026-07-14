"""
M-MEMBERSHIP: Membership Checker Module
=======================================
PURPOSE: Verify user membership in target group
SCOPE: Telegram API calls for membership verification
DEPENDS: M-CONFIG
"""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from src.config import config

logger = logging.getLogger("anon_bot")


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Membership Checker Module

PURPOSE:
    Verify that users are members of the target group before accepting questions.

INPUTS:
    - bot: Bot — Aiogram Bot instance
    - user_id: int — Telegram user ID
    - group_id: int — Target group ID

OUTPUTS:
    - is_member: bool — True if user is group member

ERRORS:
    - API_ERROR: Telegram API error
    - GROUP_NOT_FOUND: Group not accessible

EXPORTS:
    - is_group_member: Check group membership
    - get_member_status: Get detailed member status
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. is_group_member — Main membership check function
    2. get_member_status — Get detailed member status
    3. is_admin — Check if user is admin
"""

# ==============================================================================
# START_BLOCK: is_group_member
# ==============================================================================

async def is_group_member(
    bot: Bot,
    user_id: int,
    group_id: Optional[int] = None
) -> bool:
    """
    Check if user is a member of the target group.
    
    Valid member statuses: member, administrator, creator
    Invalid statuses: left, kicked, restricted
    
    Args:
        bot: Aiogram Bot instance
        user_id: Telegram user ID
        group_id: Target group ID (uses config.GROUP_ID if not provided)
        
    Returns:
        bool: True if user is a member, False otherwise
    """
    if group_id is None:
        group_id = config.GROUP_ID
    
    try:
        logger.info(
            f"[M-MEMBERSHIP][is_group_member][CHECK] "
            f"Checking user {user_id} in group {group_id}"
        )
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        
        # Valid member statuses
        valid_statuses = {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,  # Owner/Creator
            ChatMemberStatus.RESTRICTED  # Restricted users are still members
        }
        
        is_member = member.status in valid_statuses
        
        logger.info(
            f"[M-MEMBERSHIP][is_group_member][RESULT] "
            f"User {user_id}: status={member.status}, is_member={is_member}"
        )
        
        return is_member
        
    except Exception as e:
        logger.error(
            f"[M-MEMBERSHIP][is_group_member][ERROR] "
            f"Failed to check membership for user {user_id} in group {group_id}: {type(e).__name__}: {e}"
        )
        return False

# ==============================================================================
# END_BLOCK: is_group_member
# ==============================================================================


# ==============================================================================
# START_BLOCK: get_member_status
# ==============================================================================

async def get_member_status(
    bot: Bot,
    user_id: int,
    group_id: Optional[int] = None
) -> Optional[str]:
    """
    Get detailed member status for a user.
    
    Args:
        bot: Aiogram Bot instance
        user_id: Telegram user ID
        group_id: Target group ID (uses config.GROUP_ID if not provided)
        
    Returns:
        str: Member status (member, administrator, creator, left, kicked, restricted)
        None: If unable to determine status
    """
    if group_id is None:
        group_id = config.GROUP_ID
    
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        return member.status
        
    except Exception as e:
        logger.error(
            f"[M-MEMBERSHIP][get_member_status][ERROR] "
            f"Failed to get status for user {user_id}: {e}"
        )
        return None

# ==============================================================================
# END_BLOCK: get_member_status
# ==============================================================================


# ==============================================================================
# START_BLOCK: is_admin
# ==============================================================================

async def is_admin(
    bot: Bot,
    user_id: int,
    group_id: Optional[int] = None
) -> bool:
    """
    Check if user is an admin or creator of the group.
    
    Args:
        bot: Aiogram Bot instance
        user_id: Telegram user ID
        group_id: Target group ID (uses config.GROUP_ID if not provided)
        
    Returns:
        bool: True if user is admin or creator
    """
    if group_id is None:
        group_id = config.GROUP_ID
    
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        
        admin_statuses = {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        }
        
        is_admin_user = member.status in admin_statuses
        
        logger.debug(
            f"[M-MEMBERSHIP][is_admin][CHECK] "
            f"User {user_id} in group {group_id}: is_admin={is_admin_user}"
        )
        
        return is_admin_user
        
    except Exception as e:
        logger.error(
            f"[M-MEMBERSHIP][is_admin][ERROR] "
            f"Failed to check admin status for user {user_id}: {e}"
        )
        return False

# ==============================================================================
# END_BLOCK: is_admin
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Implemented is_group_member with proper status checking
    - Added get_member_status for detailed status information
    - Added is_admin helper for admin command authorization
    - All functions handle API errors gracefully
    - Uses ChatMemberStatus enum for type safety
"""

