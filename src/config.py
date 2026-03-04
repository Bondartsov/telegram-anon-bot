"""
M-CONFIG: Configuration Module
===============================
PURPOSE: Load and validate environment configuration
SCOPE: Bot settings, rate limits, logging configuration
DEPENDS: none
"""

import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """
    Bot configuration loaded from environment variables.

    Required variables (must be set in .env):
        BOT_TOKEN  — Telegram bot token from @BotFather
        GROUP_ID   — Target group ID (negative number for supergroups)
        ADMIN_ID   — Telegram user ID of the moderator/admin

    Optional variables:
        RATE_LIMIT — Questions per hour per user (default: 10)
        LOG_LEVEL  — Logging level (default: INFO)
        DB_PATH    — Path to SQLite database (default: data/bot.db)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Required settings
    BOT_TOKEN: str = Field(..., description="Telegram bot token from @BotFather")
    GROUP_ID: int = Field(..., description="Target group ID (negative for supergroups)")
    ADMIN_ID: int = Field(..., description="Telegram user ID of the moderator")

    # Optional settings with defaults
    RATE_LIMIT: int = Field(default=10, ge=1, le=100, description="Questions per hour per user")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DB_PATH: str = Field(default="data/bot.db", description="Path to SQLite database")

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_token(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("MISSING_TOKEN: BOT_TOKEN is required")
        if ":" not in v:
            raise ValueError("INVALID_TOKEN: BOT_TOKEN format is invalid")
        return v.strip()

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper().strip()
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL. Must be one of: {valid_levels}")
        return v


@lru_cache(maxsize=1)
def get_config() -> BotConfig:
    """Get cached configuration instance (loaded once at startup)."""
    return BotConfig()


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger("anon_bot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


config = get_config()
