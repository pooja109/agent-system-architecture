"""
Utility functions for the communication agent.
"""
import os
import logging
from typing import Literal
from models import EvaluationFeedback
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from models import EmailTask

logger = logging.getLogger(__name__)

def evaluate_score(feedback: EvaluationFeedback) -> Literal["pass", "fail"]:
    """Evaluate the overall score based on feedback fields."""
    bool_fields = [
        feedback.profanity,
        feedback.bias,
        feedback.misleading_claims,
        feedback.aggressive_language,
        feedback.privacy_violation,
        feedback.tone_misalignment,
        feedback.sensitive_topics,
    ]
    # If all are False, then pass; else fail
    return "pass" if not any(bool_fields) else "fail"

def custom_input_transform(input_message: EmailTask) -> ChatMessageContent:
    """Transform EmailTask to ChatMessageContent."""
    return ChatMessageContent(role=AuthorRole.USER, content=input_message.model_dump_json())

def read_from_source(folder: str, filename: str) -> str:
    """Read content from a file in the source folder."""
    filepath = os.path.join(folder, filename)
    if not os.path.exists(folder):
        logger.warning("Warning: Folder '%s' does not exist. Returning empty string.", folder)
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Warning: File '%s' not found. Returning empty string.", filepath)
        return ""
    except Exception as e:
        logger.error("Error reading file '%s': %s. Returning empty string.", filepath, e)
        return ""

def save_string_to_file(folder: str, content, filename: str) -> None:
    """Save content to a file in the specified folder."""
    filepath = os.path.join(folder, filename)
    if hasattr(content, "content"):
        content = content.content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
