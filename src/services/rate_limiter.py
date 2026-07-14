"""
M-RATE-LIMIT: Rate Limiter Module
=================================
PURPOSE: In-memory rate limiting for question submissions
SCOPE: Track user submissions, enforce hourly limits
DEPENDS: none
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger("anon_bot")


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Rate Limiter Module

PURPOSE:
    In-memory rate limiting to prevent spam and abuse.

INPUTS:
    - user_id: int — Telegram user ID
    - limit: int — Maximum submissions per hour

OUTPUTS:
    - allowed: bool — Whether submission is allowed
    - remaining: int — Remaining submissions in current window
    - reset_in: int — Seconds until limit resets

ERRORS:
    - RATE_EXCEEDED: User has exceeded rate limit (handled gracefully)

EXPORTS:
    - RateLimiter: Rate limiter class
    - check_limit: Check if user can submit
    - record_submission: Record new submission
    - cleanup_old: Remove expired entries
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. RateLimitEntry — Dataclass for tracking submissions
    2. RateLimiter — Main rate limiter class with sliding window
"""

# ==============================================================================
# START_BLOCK: RateLimitEntry
# ==============================================================================

@dataclass
class RateLimitEntry:
    """
    Represents a single submission timestamp.
    
    Attributes:
        timestamp: Unix timestamp of submission
    """
    timestamp: float

# ==============================================================================
# END_BLOCK: RateLimitEntry
# ==============================================================================


# ==============================================================================
# START_BLOCK: RateLimiter
# ==============================================================================

class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    
    Tracks submissions per user within a configurable time window.
    Automatically cleans up expired entries.
    
    Attributes:
        limit: Maximum submissions per window
        window_seconds: Time window in seconds (default: 3600 = 1 hour)
        submissions: Dictionary mapping user_id to list of submissions
    """
    
    def __init__(self, limit: int = 10, window_seconds: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            limit: Maximum submissions per window (default: 10)
            window_seconds: Window duration in seconds (default: 3600 = 1 hour)
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.submissions: Dict[int, List[RateLimitEntry]] = defaultdict(list)
        
        logger.info(
            f"[M-RATE-LIMIT][__init__][INIT] "
            f"Rate limiter initialized: {limit} submissions per {window_seconds}s"
        )
    
    def check_limit(self, user_id: int) -> dict:
        """
        Check if user can submit a new question.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            dict with keys:
                - allowed: bool — Whether submission is allowed
                - remaining: int — Remaining submissions
                - reset_in: int — Seconds until oldest entry expires
                - current: int — Current submission count
        """
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Get user's submissions and filter out expired ones
        user_submissions = self.submissions.get(user_id, [])
        active_submissions = [s for s in user_submissions if s.timestamp > cutoff]
        
        # Update stored submissions (cleanup)
        self.submissions[user_id] = active_submissions
        
        current_count = len(active_submissions)
        remaining = max(0, self.limit - current_count)
        allowed = current_count < self.limit
        
        # Calculate when the oldest submission will expire
        if active_submissions:
            oldest = min(s.timestamp for s in active_submissions)
            reset_in = int(oldest + self.window_seconds - now)
        else:
            reset_in = 0
        
        result = {
            "allowed": allowed,
            "remaining": remaining,
            "reset_in": max(0, reset_in),
            "current": current_count
        }
        
        logger.debug(
            f"[M-RATE-LIMIT][check_limit][CHECK] "
            f"User {user_id}: allowed={allowed}, remaining={remaining}, reset_in={reset_in}s"
        )
        
        return result
    
    def record_submission(self, user_id: int) -> None:
        """
        Record a new submission for a user.
        
        Args:
            user_id: Telegram user ID
        """
        now = time.time()
        entry = RateLimitEntry(timestamp=now)
        self.submissions[user_id].append(entry)
        
        logger.info(
            f"[M-RATE-LIMIT][record_submission][RECORD] "
            f"Submission recorded for user {user_id}"
        )
    
    def cleanup_old(self) -> int:
        """
        Remove all expired entries from memory.
        
        Returns:
            int: Number of entries removed
        """
        now = time.time()
        cutoff = now - self.window_seconds
        removed = 0
        
        for user_id in list(self.submissions.keys()):
            original_count = len(self.submissions[user_id])
            self.submissions[user_id] = [
                s for s in self.submissions[user_id] if s.timestamp > cutoff
            ]
            removed += original_count - len(self.submissions[user_id])
            
            # Remove empty lists
            if not self.submissions[user_id]:
                del self.submissions[user_id]
        
        if removed > 0:
            logger.info(
                f"[M-RATE-LIMIT][cleanup_old][CLEANUP] "
                f"Removed {removed} expired entries"
            )
        
        return removed
    
    def get_user_count(self, user_id: int) -> int:
        """
        Get current submission count for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            int: Number of active submissions
        """
        now = time.time()
        cutoff = now - self.window_seconds
        return len([s for s in self.submissions.get(user_id, []) if s.timestamp > cutoff])
    
    def reset_user(self, user_id: int) -> None:
        """
        Reset rate limit for a specific user (admin function).
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self.submissions:
            del self.submissions[user_id]
            logger.info(
                f"[M-RATE-LIMIT][reset_user][RESET] "
                f"Rate limit reset for user {user_id}"
            )

# ==============================================================================
# END_BLOCK: RateLimiter
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Created RateLimitEntry dataclass for tracking submissions
    - Implemented RateLimiter with sliding window algorithm
    - Added check_limit, record_submission, cleanup_old methods
    - Automatic cleanup of expired entries on check
    - Support for configurable limit and window duration
"""

# Global rate limiter instance - lazy initialization
_rate_limiter: RateLimiter = None

def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.config import config
        _rate_limiter = RateLimiter(limit=config.RATE_LIMIT)
    return _rate_limiter

# For backward compatibility
rate_limiter = property(lambda self: get_rate_limiter())

