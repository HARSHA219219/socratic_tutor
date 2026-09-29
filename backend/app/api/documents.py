from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_principal
from app.db.database import get_db
from app.models.domain import Message, Session
from app.services.document_storage import resolve_document_path

router = APIRouter()

@router.get("/{message_id}")
async def get_message_document(
    message_id: str,
    principal: dict = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Serves a chat document to its owning student or to the admin."""
    not_found = HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(Message, Session.student_id)
        .join(Session, Session.id == Message.session_id)
        .where(Message.id == message_id)
    )
    row = result.first()
    if not row or not row[0].document_key:
        raise not_found
    message, owner_id = row
    if principal["kind"] == "student" and principal["id"] != owner_id:
        raise not_found
    try:
        path = resolve_document_path(message.document_key)
    except ValueError:
        raise not_found
    if not path.is_file():
        raise not_found
    return FileResponse(
        path,
        media_type=message.document_mime_type,
        filename=message.document_name,  # sent as an attachment; sanitized at upload
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )
