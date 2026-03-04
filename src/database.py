"""
M-DB: Database Module
=====================
PURPOSE: Persistent storage for questions, users, and group configs
SCOPE: SQLite operations, schema management, CRUD operations
DEPENDS: none
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger("anon_bot")


# ==============================================================================
# Schema
# ==============================================================================

SCHEMA_USERS = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_QUESTIONS = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    media_type TEXT,
    media_file_id TEXT,
    group_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    topic_message_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);
"""

SCHEMA_GROUP_CONFIGS = """
CREATE TABLE IF NOT EXISTS group_configs (
    group_id INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_QUESTIONS_USER = """
CREATE INDEX IF NOT EXISTS idx_questions_user_id
ON questions(user_id, created_at DESC);
"""

INDEX_QUESTIONS_DELETED = """
CREATE INDEX IF NOT EXISTS idx_questions_deleted
ON questions(is_deleted, created_at DESC);
"""


# ==============================================================================
# init_db
# ==============================================================================

async def init_db(db_path: str = "data/bot.db") -> aiosqlite.Connection:
    """Initialize database and create tables."""
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute(SCHEMA_USERS)
        await db.execute(SCHEMA_QUESTIONS)
        await db.execute(SCHEMA_GROUP_CONFIGS)
        await db.execute(INDEX_QUESTIONS_USER)
        await db.execute(INDEX_QUESTIONS_DELETED)
        await db.commit()
        logger.info(f"[M-DB][init_db][INIT] Database initialized at {db_path}")
        return db
    except Exception as e:
        logger.error(f"[M-DB][init_db][ERROR] Failed to initialize database: {e}")
        raise RuntimeError(f"DB_INIT_FAILED: {e}")


# ==============================================================================
# User operations
# ==============================================================================

async def ensure_user(
    db: aiosqlite.Connection,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> None:
    """Ensure user exists in database (upsert)."""
    await db.execute(
        """
        INSERT INTO users (telegram_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name
        """,
        (telegram_id, username, first_name, last_name)
    )
    await db.commit()


# ==============================================================================
# Question operations
# ==============================================================================

async def get_user_questions(
    db: aiosqlite.Connection,
    user_id: int,
    limit: int = 5,
    hours: int = 24
) -> list:
    """Get user's recent non-deleted questions."""
    cutoff = datetime.now() - timedelta(hours=hours)
    async with db.execute(
        """
        SELECT id, content, created_at, topic_message_id, topic_id, group_id
        FROM questions
        WHERE user_id = ?
          AND is_deleted = FALSE
          AND created_at >= ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, cutoff.isoformat(), limit)
    ) as cursor:
        rows = await cursor.fetchall()

    questions = []
    for row in rows:
        content = row["content"]
        questions.append({
            "id": row["id"],
            "content": content[:47] + "..." if len(content) > 50 else content,
            "full_content": content,
            "created_at": row["created_at"],
            "topic_message_id": row["topic_message_id"],
            "topic_id": row["topic_id"],
            "group_id": row["group_id"]
        })
    return questions


async def delete_question(
    db: aiosqlite.Connection,
    question_id: str,
    user_id: int
) -> Optional[dict]:
    """Mark a question as deleted and return its topic info."""
    async with db.execute(
        "SELECT topic_message_id, topic_id, group_id, is_deleted FROM questions WHERE id = ? AND user_id = ?",
        (question_id, user_id)
    ) as cursor:
        row = await cursor.fetchone()

    if not row or row["is_deleted"]:
        return None

    await db.execute("UPDATE questions SET is_deleted = TRUE WHERE id = ?", (question_id,))
    await db.commit()
    logger.info(f"[M-DB][delete_question][DELETE] Question {question_id} marked as deleted")
    return {
        "topic_message_id": row["topic_message_id"],
        "topic_id": row["topic_id"],
        "group_id": row["group_id"]
    }


# ==============================================================================
# Group config operations
# ==============================================================================

async def get_group_config(
    db: aiosqlite.Connection,
    group_id: int
) -> Optional[int]:
    """Get configured topic ID for a specific group."""
    async with db.execute(
        "SELECT topic_id FROM group_configs WHERE group_id = ?",
        (group_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row:
        return row["topic_id"]
    return None


async def set_group_config(
    db: aiosqlite.Connection,
    group_id: int,
    topic_id: int
) -> None:
    """Set or update topic configuration for a group."""
    await db.execute(
        """
        INSERT INTO group_configs (group_id, topic_id, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(group_id) DO UPDATE SET
            topic_id = excluded.topic_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (group_id, topic_id)
    )
    await db.commit()
    logger.info(f"[M-DB][set_group_config][SET] Group {group_id} configured with topic {topic_id}")


async def get_latest_group_config(
    db: aiosqlite.Connection,
) -> Optional[tuple]:
    """
    Get the most recently configured group and topic.

    This is the primary way to resolve the active publishing target.
    Updated every time /set_topic is called in a group.

    Returns:
        tuple: (group_id, topic_id) or None if no config exists
    """
    async with db.execute(
        "SELECT group_id, topic_id FROM group_configs ORDER BY updated_at DESC LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        logger.debug(
            f"[M-DB][get_latest_group_config][GET] "
            f"Latest config: group {row['group_id']}, topic {row['topic_id']}"
        )
        return row["group_id"], row["topic_id"]

    logger.debug("[M-DB][get_latest_group_config][NOT_FOUND] No group config found")
    return None


# ==============================================================================
# Moderation operations
# ==============================================================================

async def save_pending_question(
    db: aiosqlite.Connection,
    user_id: int,
    content: str,
    group_id: int,
    topic_id: int,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None
) -> str:
    """Save a pending question for moderation. Returns question UUID."""
    question_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO questions
        (id, user_id, content, media_type, media_file_id, group_id, topic_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        (question_id, user_id, content, media_type, media_file_id, group_id, topic_id)
    )
    await db.commit()
    logger.info(f"[M-DB][save_pending_question][SAVE] Pending question {question_id} for user {user_id}")
    return question_id


async def approve_question(
    db: aiosqlite.Connection,
    question_id: str,
    topic_message_id: int
) -> bool:
    """Approve a pending question and record the posted message ID."""
    await db.execute(
        "UPDATE questions SET status = 'approved', topic_message_id = ? WHERE id = ? AND status = 'pending'",
        (topic_message_id, question_id)
    )
    await db.commit()
    logger.info(f"[M-DB][approve_question][APPROVE] Question {question_id} approved")
    return True


async def reject_question(
    db: aiosqlite.Connection,
    question_id: str
) -> bool:
    """Reject a pending question."""
    result = await db.execute(
        "UPDATE questions SET status = 'rejected' WHERE id = ? AND status = 'pending'",
        (question_id,)
    )
    await db.commit()
    if result.rowcount > 0:
        logger.info(f"[M-DB][reject_question][REJECT] Question {question_id} rejected")
        return True
    return False


async def get_user_id_by_question(
    db: aiosqlite.Connection,
    question_id: str
) -> Optional[int]:
    """Get user_id for a question."""
    async with db.execute("SELECT user_id FROM questions WHERE id = ?", (question_id,)) as cursor:
        row = await cursor.fetchone()
    return row["user_id"] if row else None


async def get_question_by_id(
    db: aiosqlite.Connection,
    question_id: str
) -> Optional[dict]:
    """Get full question data by ID."""
    async with db.execute(
        "SELECT id, user_id, content, media_type, media_file_id, group_id, topic_id, status FROM questions WHERE id = ?",
        (question_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "content": row["content"],
        "media_type": row["media_type"],
        "media_file_id": row["media_file_id"],
        "group_id": row["group_id"],
        "topic_id": row["topic_id"],
        "status": row["status"]
    }


async def get_moderation_history(
    db: aiosqlite.Connection,
    limit: int = 20
) -> list:
    """Get moderation history for admin."""
    async with db.execute(
        """
        SELECT id, content, status, created_at, media_type, media_file_id, user_id
        FROM questions
        WHERE status IN ('approved', 'rejected')
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    ) as cursor:
        rows = await cursor.fetchall()

    history = []
    for row in rows:
        content = row["content"]
        history.append({
            "id": row["id"],
            "content": content[:97] + "..." if len(content) > 100 else content,
            "full_content": content,
            "status": row["status"],
            "created_at": row["created_at"],
            "media_type": row["media_type"],
        })
    return history


async def get_stats(db: aiosqlite.Connection) -> dict:
    """Get moderation statistics."""
    stats = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
    async with db.execute(
        "SELECT status, COUNT(*) as count FROM questions GROUP BY status"
    ) as cursor:
        rows = await cursor.fetchall()
    for row in rows:
        stats[row["status"]] = row["count"]
        stats["total"] += row["count"]
    return stats
