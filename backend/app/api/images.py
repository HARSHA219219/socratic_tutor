from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_principal
from app.db.database import get_db
from app.models.domain import Message, Session
from app.services.image_storage import resolve_image_path

router = APIRouter()

@router.get("/{message_id}")
async def get_message_image(
    message_id: str,
    principal: dict = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Serves a chat image to its owning student or to the admin."""
    not_found = HTTPException(status_code=404, detail="Image not found")
    result = await db.execute(
        select(Message, Session.student_id)
        .join(Session, Session.id == Message.session_id)
        .where(Message.id == message_id)
    )
    row = result.first()
    if not row or not row[0].image_key:
        raise not_found
    message, owner_id = row
    if principal["kind"] == "student" and principal["id"] != owner_id:
        raise not_found
    try:
        path = resolve_image_path(message.image_key)
    except ValueError:
        raise not_found
    if not path.is_file():
        raise not_found
    return FileResponse(
        path,
        media_type=message.image_mime_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
