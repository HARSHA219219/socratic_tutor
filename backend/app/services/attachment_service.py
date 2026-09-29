"""Multiple attachments per message: validation, context budgeting, storage and image summaries.

Images and documents keep their existing per-file rules (image_storage / document_storage).
On top of that a message may carry at most MAX_ATTACHMENTS_PER_MESSAGE files totalling
MAX_TOTAL_ATTACHMENT_BYTES, and their estimated prompt content must fit in
ATTACHMENT_CONTEXT_PERCENT of CONTEXT_TOKEN_BUDGET.
"""
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from fastapi import UploadFile
from sqlalchemy.future import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.domain import MessageAttachment
from app.services.document_storage import (
    DocumentError, extract_text, resolve_document_path, sanitize_display_name, sanitize_filename, save_document,
    validate_document,
)
from app.services.image_storage import detect_image_type, load_image_data_url, resolve_image_path, save_image, validate_upload
from app.services.token_estimator import IMAGE_TOKENS, estimate_tokens

logger = logging.getLogger(__name__)

_IMAGE_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
# Instruction wrapper added around each document's text in the prompt
_DOCUMENT_WRAPPER_TOKENS = 60


class AttachmentError(Exception):
    """A user-facing problem with the uploaded attachments."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class PreparedAttachment:
    """A validated upload, not yet written to disk."""
    kind: str  # "image" | "document"
    data: bytes
    mime: str
    name: str
    text: Optional[str] = None
    text_status: Optional[str] = None

    @property
    def estimated_tokens(self) -> int:
        """Conservative prompt cost (image tokens depend on size/detail, so they are estimated high)."""
        if self.kind == "image":
            return IMAGE_TOKENS
        if self.text_status == "image":  # PDF without text: sent as rendered page images
            return settings.MAX_PDF_IMAGE_PAGES * IMAGE_TOKENS
        return estimate_tokens(self.text or "") + _DOCUMENT_WRAPPER_TOKENS


def attachment_token_cap() -> int:
    return settings.CONTEXT_TOKEN_BUDGET * settings.ATTACHMENT_CONTEXT_PERCENT // 100


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):g} MB"


def prepare_image(data: bytes, filename: str) -> PreparedAttachment:
    mime, error = validate_upload(data)
    if error:
        raise AttachmentError(error, 413 if len(data) > settings.MAX_IMAGE_BYTES else 400)
    return PreparedAttachment("image", data, mime, sanitize_display_name(filename, _IMAGE_EXT[mime], "image"))


async def prepare_document(data: bytes, filename: str) -> PreparedAttachment:
    try:
        mime = validate_document(data, filename)
        # Extraction is CPU-bound; keep it off the event loop
        text, status = await asyncio.to_thread(extract_text, data, mime)
    except DocumentError as e:
        raise AttachmentError(e.message, e.status_code) from e
    return PreparedAttachment("document", data, mime, sanitize_filename(filename, mime), text, status)


def check_context_budget(prepared: Sequence[PreparedAttachment]) -> None:
    """Rejects attachments whose combined content would crowd out the conversation."""
    cap = attachment_token_cap()
    total = sum(p.estimated_tokens for p in prepared)
    if total <= cap:
        return
    detail = ", ".join(f'"{p.name}" ~{p.estimated_tokens:,}' for p in prepared)
    raise AttachmentError(
        f"These attachments are too large for the tutor to read together (about {total:,} tokens; "
        f"one message can use up to {cap:,}). Per file: {detail}. "
        "Remove a file, send it in a separate message, or upload a shorter document.",
        413,
    )


async def read_uploads(files: Sequence[UploadFile]) -> list[PreparedAttachment]:
    """Validates every file (type from content, per-file size, count, total size, context budget)
    before anything is stored, so a message is saved with all of its files or none."""
    files = [f for f in files if f is not None]
    if not files:
        raise AttachmentError("Attach at least one file.")
    if len(files) > settings.MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentError(f"You can attach up to {settings.MAX_ATTACHMENTS_PER_MESSAGE} files per message.")

    per_file_cap = max(settings.MAX_IMAGE_BYTES, settings.MAX_DOCUMENT_BYTES)
    total = 0
    prepared: list[PreparedAttachment] = []
    for upload in files:
        # Never buffer more than one byte over the largest per-file limit
        data = await upload.read(per_file_cap + 1)
        total += len(data)
        if total > settings.MAX_TOTAL_ATTACHMENT_BYTES:
            raise AttachmentError(
                f"Attachments are too large together (max {_mb(settings.MAX_TOTAL_ATTACHMENT_BYTES)} per message).", 413
            )
        filename = upload.filename or ""
        label = sanitize_display_name(filename, "", "file").rstrip(".") or "file"
        try:
            if detect_image_type(data):
                prepared.append(prepare_image(data, filename))
            else:
                prepared.append(await prepare_document(data, filename))
        except AttachmentError as e:
            message = e.message
            if message.startswith("Unsupported file type"):
                message = "Unsupported file type. You can attach images (JPG, PNG, WebP) or PDF, DOCX and TXT files."
            raise AttachmentError(f'"{label}": {message}', e.status_code) from e
    check_context_budget(prepared)
    return prepared


# ---------- storage ----------

def resolve_attachment_path(kind: str, key: str) -> Path:
    return resolve_image_path(key) if kind == "image" else resolve_document_path(key)


def delete_stored(saved: Sequence[tuple[PreparedAttachment, str]]) -> None:
    for p, key in saved:
        try:
            resolve_attachment_path(p.kind, key).unlink(missing_ok=True)
        except (OSError, ValueError):
            logger.warning(f"Could not remove attachment file {key}")


async def store_attachments(prepared: Sequence[PreparedAttachment]) -> list[tuple[PreparedAttachment, str]]:
    """Writes files under random names; removes the ones already written if any write fails."""
    saved: list[tuple[PreparedAttachment, str]] = []
    try:
        for p in prepared:
            key = await (save_image(p.data, p.mime) if p.kind == "image" else save_document(p.data, p.mime))
            saved.append((p, key))
    except Exception:
        delete_stored(saved)
        raise
    return saved


# ---------- image summaries ----------

async def summarize_message_images(message_id: str) -> None:
    """Describes each new image of a message once (after the tutor has seen the original).
    Runs as a background task with its own DB session; failures are recorded, never raised."""
    if not settings.IMAGE_SUMMARY_ENABLED:
        return
    from app.services.llm_service import describe_image  # avoid an import cycle

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MessageAttachment).where(
                    MessageAttachment.message_id == message_id,
                    MessageAttachment.kind == "image",
                    MessageAttachment.summary_status.is_(None),
                )
            )
            pending = result.scalars().all()
            for att in pending:
                data_url = await load_image_data_url(att.storage_key, att.mime_type)
                summary = await describe_image(db, data_url) if data_url else None
                att.image_summary = summary
                att.summary_status = "ok" if summary else "failed"
            if pending:
                await db.commit()
    except Exception as e:
        logger.error(f"Image summary failed for message {message_id}: {e}")
