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


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Configuration Module

PURPOSE:
    Load and validate environment configuration for the Telegram bot.

INPUTS:
    - Environment variables: BOT_TOKEN, GROUP_ID, RATE_LIMIT, LOG_LEVEL

OUTPUTS:
    - config: BotConfig — Validated configuration object

ERRORS:
    - MISSING_TOKEN: BOT_TOKEN not provided or empty
    - MISSING_GROUP_ID: GROUP_ID not provided or invalid

EXPORTS:
    - config: Global configuration instance
    - BotConfig: Configuration dataclass
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. BotConfig — Pydantic settings model with validation
    2. get_config — Cached configuration loader
    3. setup_logging — Logging configuration helper
"""

# ==============================================================================
# START_BLOCK: BotConfig
# ==============================================================================

class BotConfig(BaseSettings):
    """
    Bot configuration loaded from environment variables.
    
    Attributes:
        BOT_TOKEN: Telegram bot token from @BotFather
        GROUP_ID: Target group ID (negative number for supergroups)
        ADMIN_ID: Admin user ID for moderation
        RATE_LIMIT: Maximum questions per hour per user
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
        DB_PATH: Path to SQLite database file
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Required settings
    BOT_TOKEN: str = Field(..., description="Telegram bot token from @BotFather")
    GROUP_ID: int = Field(..., description="Target group ID")
    ADMIN_ID: int = Field(..., description="Admin user ID for moderation")

    # Optional settings with defaults
    RATE_LIMIT: int = Field(default=10, ge=1, le=100, description="Questions per hour per user")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DB_PATH: str = Field(default="data/bot.db", description="Path to SQLite database")
    
    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate bot token format."""
        if not v or not v.strip():
            raise ValueError("MISSING_TOKEN: BOT_TOKEN is required")
        if ":" not in v:
            raise ValueError("INVALID_TOKEN: BOT_TOKEN format is invalid")
        return v.strip()
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate and normalize log level."""
        v = v.upper().strip()
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL. Must be one of: {valid_levels}")
        return v

# ==============================================================================
# END_BLOCK: BotConfig
# ==============================================================================


# ==============================================================================
# START_BLOCK: get_config
# ==============================================================================

@lru_cache(maxsize=1)
def get_config() -> BotConfig:
    """
    Get cached configuration instance.
    
    Uses lru_cache to ensure configuration is loaded only once.
    
    Returns:
        BotConfig: Validated configuration object
        
    Raises:
        ValidationError: If required environment variables are missing
    """
    return BotConfig()

# ==============================================================================
# END_BLOCK: get_config
# ==============================================================================


# ==============================================================================
# START_BLOCK: setup_logging
# ==============================================================================

def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("anon_bot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

# ==============================================================================
# END_BLOCK: setup_logging
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Created BotConfig with Pydantic settings validation
    - Implemented get_config with LRU cache for singleton pattern
    - Added setup_logging helper for consistent logging
    - All environment variables validated at startup
"""

# Global config instance (lazy loaded via get_config)
config = get_config()

