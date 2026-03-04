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


@dataclass
class RateLimitEntry:
    timestamp: float


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    Tracks submissions per user within a configurable time window.
    Automatically cleans up expired entries on each check.
    """

    def __init__(self, limit: int = 10, window_seconds: int = 3600):
        self.limit = limit
        self.window_seconds = window_seconds
        self.submissions: Dict[int, List[RateLimitEntry]] = defaultdict(list)
        logger.info(f"[M-RATE-LIMIT][__init__][INIT] Rate limiter initialized: {limit} submissions per {window_seconds}s")

    def check_limit(self, user_id: int) -> dict:
        """Check if user can submit. Returns dict with allowed, remaining, reset_in, current."""
        now = time.time()
        cutoff = now - self.window_seconds
        active = [s for s in self.submissions.get(user_id, []) if s.timestamp > cutoff]
        self.submissions[user_id] = active
        current_count = len(active)
        reset_in = int(min(s.timestamp for s in active) + self.window_seconds - now) if active else 0
        return {
            "allowed": current_count < self.limit,
            "remaining": max(0, self.limit - current_count),
            "reset_in": max(0, reset_in),
            "current": current_count
        }

    def record_submission(self, user_id: int) -> None:
        """Record a new submission for a user."""
        self.submissions[user_id].append(RateLimitEntry(timestamp=time.time()))
        logger.info(f"[M-RATE-LIMIT][record_submission][RECORD] Submission recorded for user {user_id}")


_rate_limiter: RateLimiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create singleton rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.config import config
        _rate_limiter = RateLimiter(limit=config.RATE_LIMIT)
    return _rate_limiter
