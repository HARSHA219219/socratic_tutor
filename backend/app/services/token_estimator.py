"""Conservative token estimates for prompt budgeting.

No tokenizer is installed, so this over-estimates on purpose: ~3 characters per
token (English averages ~4) plus per-message overhead, and a flat cost per image.
Swap `estimate_tokens` for a model-specific tokenizer (e.g. tiktoken) later
without touching callers.
"""
import math
from typing import Any, Iterable

CHARS_PER_TOKEN = 3.0
MESSAGE_OVERHEAD_TOKENS = 6
IMAGE_TOKENS = 1100  # roughly a high-detail image on common vision models


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text or "") / CHARS_PER_TOKEN)


def _content_tokens(content: Any) -> int:
    if isinstance(content, str):
        return estimate_tokens(content)
    total = 0
    for part in content or []:
        if part.get("type") == "image_url":
            total += IMAGE_TOKENS
        else:
            total += estimate_tokens(part.get("text", ""))
    return total


def estimate_messages_tokens(messages: Iterable[dict]) -> int:
    """Estimated prompt size of an OpenAI-style messages list."""
    return sum(MESSAGE_OVERHEAD_TOKENS + _content_tokens(m.get("content")) for m in messages)
