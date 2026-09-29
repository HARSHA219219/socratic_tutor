from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_principal
from app.db.database import get_db
from app.models.domain import Message, MessageAttachment, Session
from app.services.attachment_service import resolve_attachment_path

router = APIRouter()

@router.get("/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    principal: dict = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Serves one attachment (image or document) to its owning student or to the admin."""
    not_found = HTTPException(status_code=404, detail="Attachment not found")
    result = await db.execute(
        select(MessageAttachment, Session.student_id)
        .join(Message, Message.id == MessageAttachment.message_id)
        .join(Session, Session.id == Message.session_id)
        .where(MessageAttachment.id == attachment_id)
    )
    row = result.first()
    if not row:
        raise not_found
    att, owner_id = row
    if principal["kind"] == "student" and principal["id"] != owner_id:
        raise not_found
    try:
        path = resolve_attachment_path(att.kind, att.storage_key)
    except ValueError:
        raise not_found
    if not path.is_file():
        raise not_found
    return FileResponse(
        path,
        media_type=att.mime_type,
        filename=att.name,  # sanitized at upload
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )
