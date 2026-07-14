"""
M-ANONYMIZER: Anonymizer Module
================================
PURPOSE: Strip identifying information from content
SCOPE: Extract content from messages, prepare for anonymous posting
DEPENDS: M-DB (for future content logging)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from aiogram.types import Message

logger = logging.getLogger("anon_bot")


# ==============================================================================
# MODULE_CONTRACT
# ==============================================================================
"""
Contract: Anonymizer Module

PURPOSE:
    Extract and clean message content for anonymous posting.

INPUTS:
    - message: Message — Original Telegram message

OUTPUTS:
    - content: AnonContent — Cleaned content ready for posting

ERRORS:
    - UNSUPPORTED_TYPE: Message type not supported (video, file, etc.)
    - EMPTY_CONTENT: No content to anonymize

EXPORTS:
    - AnonContent: Dataclass for anonymized content
    - prepare_content: Extract and clean message content
    - validate_content: Validate content before posting
"""

# ==============================================================================
# MODULE_MAP
# ==============================================================================
"""
BLOCKS:
    1. AnonContent — Dataclass for anonymized content
    2. prepare_content — Main content extraction function
    3. validate_content — Content validation
"""

# ==============================================================================
# START_BLOCK: AnonContent
# ==============================================================================

@dataclass
class AnonContent:
    """
    Represents anonymized content ready for posting.
    
    All identifying information has been stripped.
    Only the actual content (text, media) remains.
    
    Attributes:
        text: Text content (question text or photo caption)
        media_type: Type of media ('photo') or None for text-only
        media_file_id: Telegram file ID for media or None
        has_content: Whether there is any content to post
    """
    text: str
    media_type: Optional[str] = None
    media_file_id: Optional[str] = None
    
    @property
    def has_content(self) -> bool:
        """Check if there is any content to post."""
        return bool(self.text.strip()) or self.media_file_id is not None
    
    @property
    def is_photo(self) -> bool:
        """Check if content includes a photo."""
        return self.media_type == "photo" and self.media_file_id is not None
    
    @property
    def is_text_only(self) -> bool:
        """Check if content is text only."""
        return self.media_type is None and bool(self.text.strip())

# ==============================================================================
# END_BLOCK: AnonContent
# ==============================================================================


# ==============================================================================
# START_BLOCK: prepare_content
# ==============================================================================

def prepare_content(message: Message) -> AnonContent:
    """
    Extract and clean content from a Telegram message.
    
    Strips all identifying information and returns only the content.
    Supports: text messages, photos with captions
    
    Args:
        message: Original Telegram message
        
    Returns:
        AnonContent: Cleaned content ready for anonymous posting
        
    Raises:
        ValueError: If message type is not supported or content is empty
    """
    text = ""
    media_type = None
    media_file_id = None
    
    # Extract content based on message type
    if message.photo:
        # Photo message - get the largest photo (last in list)
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        text = message.caption or ""
        logger.debug(
            f"[M-ANONYMIZER][prepare_content][PHOTO] "
            f"Extracted photo with caption length {len(text)}"
        )
        
    elif message.text:
        # Text-only message
        text = message.text
        logger.debug(
            f"[M-ANONYMIZER][prepare_content][TEXT] "
            f"Extracted text length {len(text)}"
        )
        
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
    
    # Clean text content
    text = text.strip()
    
    # Validate we have content
    if not text and not media_file_id:
        raise ValueError("EMPTY_CONTENT: Please include your question in the message.")
    
    if media_file_id and not text:
        raise ValueError("EMPTY_CONTENT: Please add a caption with your question to the photo.")
    
    # Create anonymized content
    content = AnonContent(
        text=text,
        media_type=media_type,
        media_file_id=media_file_id
    )
    
    logger.info(
        f"[M-ANONYMIZER][prepare_content][DONE] "
        f"Prepared content: type={media_type or 'text'}, text_len={len(text)}"
    )
    
    return content

# ==============================================================================
# END_BLOCK: prepare_content
# ==============================================================================


# ==============================================================================
# START_BLOCK: validate_content
# ==============================================================================

def validate_content(content: AnonContent, max_length: int = 4000) -> tuple[bool, str]:
    """
    Validate content before posting.
    
    Args:
        content: Anonymized content to validate
        max_length: Maximum text length (Telegram limit is 4096)
        
    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not content.has_content:
        return False, "No content to post."
    
    if len(content.text) > max_length:
        return False, f"Message too long. Maximum {max_length} characters allowed."
    
    # Check for minimum meaningful content
    if len(content.text.strip()) < 3:
        return False, "Question is too short. Please provide more details."
    
    return True, ""

# ==============================================================================
# END_BLOCK: validate_content
# ==============================================================================


# ==============================================================================
# CHANGE_SUMMARY
# ==============================================================================
"""
CHANGE_SUMMARY:
    - Created AnonContent dataclass for type-safe content handling
    - Implemented prepare_content for text and photo extraction
    - Added validation for supported/unsupported message types
    - Added validate_content for pre-posting validation
    - All identifying information stripped before returning content
"""

