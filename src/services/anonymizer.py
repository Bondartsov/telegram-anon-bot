"""
M-ANONYMIZER: Anonymizer Module
================================
PURPOSE: Strip identifying information from content
SCOPE: Extract content from messages, prepare for anonymous posting
DEPENDS: none
"""

import logging
from dataclasses import dataclass
from typing import Optional

from aiogram.types import Message

logger = logging.getLogger("anon_bot")


@dataclass
class AnonContent:
    """
    Anonymized content ready for posting.
    All identifying information has been stripped.
    """
    text: str
    media_type: Optional[str] = None
    media_file_id: Optional[str] = None

    @property
    def has_content(self) -> bool:
        return bool(self.text.strip()) or self.media_file_id is not None

    @property
    def is_photo(self) -> bool:
        return self.media_type == "photo" and self.media_file_id is not None

    @property
    def is_text_only(self) -> bool:
        return self.media_type is None and bool(self.text.strip())


def prepare_content(message: Message) -> AnonContent:
    """
    Extract and clean content from a Telegram message.
    Supports: text, photos with caption.
    Raises ValueError for unsupported types.
    """
    text = ""
    media_type = None
    media_file_id = None

    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        text = message.caption or ""
    elif message.text:
        text = message.text
    elif message.video:
        raise ValueError("UNSUPPORTED_TYPE: Videos are not supported. Please send text or photo.")
    elif message.document:
        raise ValueError("UNSUPPORTED_TYPE: Documents are not supported. Please send text or photo.")
    elif message.sticker:
        raise ValueError("UNSUPPORTED_TYPE: Stickers are not supported. Please send text or photo.")
    elif message.voice:
        raise ValueError("UNSUPPORTED_TYPE: Voice messages are not supported. Please send text or photo.")
    elif message.audio:
        raise ValueError("UNSUPPORTED_TYPE: Audio files are not supported. Please send text or photo.")
    else:
        raise ValueError("UNSUPPORTED_TYPE: This message type is not supported.")

    text = text.strip()
    if not text and not media_file_id:
        raise ValueError("EMPTY_CONTENT: Please include your question in the message.")
    if media_file_id and not text:
        raise ValueError("EMPTY_CONTENT: Please add a caption with your question to the photo.")

    logger.info(f"[M-ANONYMIZER][prepare_content][DONE] Prepared content: type={media_type or 'text'}, text_len={len(text)}")
    return AnonContent(text=text, media_type=media_type, media_file_id=media_file_id)


def validate_content(content: AnonContent, max_length: int = 4000) -> tuple:
    """Validate content before posting. Returns (is_valid, error_message)."""
    if not content.has_content:
        return False, "No content to post."
    if len(content.text) > max_length:
        return False, f"Message too long. Maximum {max_length} characters allowed."
    if len(content.text.strip()) < 3:
        return False, "Question is too short. Please provide more details."
    return True, ""
