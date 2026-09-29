from pydantic import BaseModel, Field, field_validator, model_validator
import json
from typing import Optional, List
from datetime import datetime
import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

def _validate_username(v: str) -> str:
    v = v.strip()
    if not USERNAME_RE.match(v):
        raise ValueError("Username must be 3-30 characters: letters, numbers, '_', '.' or '-'")
    return v

def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password is too long (max 72 bytes)")
    return v

class StudentBase(BaseModel):
    name: str
    roll_no: str

class StudentCreate(StudentBase):
    pass

class StudentSignup(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    roll_no: str = Field(min_length=1, max_length=50)
    username: str
    password: str

    _u = field_validator("username")(_validate_username)
    _p = field_validator("password")(_validate_password)

    @field_validator("name", "roll_no")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field is required")
        return v

class StudentLoginRequest(BaseModel):
    username: str
    password: str

class RecoveryVerifyRequest(BaseModel):
    username: str
    recovery_code: str

class RecoveryVerifyResponse(BaseModel):
    reset_token: str

class PasswordResetRequest(BaseModel):
    reset_token: str
    new_password: str

    _p = field_validator("new_password")(_validate_password)

class StudentResponse(StudentBase):
    id: str
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class StudentAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: StudentResponse
    # Present only right after signup/reset; shown to the student exactly once
    recovery_code: Optional[str] = None

class SessionCreate(BaseModel):
    student_id: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    student_id: str
    title: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    role: str
    content: str

class AttachmentResponse(BaseModel):
    id: str
    position: int
    kind: str  # "image" | "document"
    name: Optional[str] = None
    mime_type: str
    size_bytes: int
    # Documents: "ok" | "truncated" | "image"; the extracted text itself stays server-side
    text_status: Optional[str] = None
    # Images: description reused in later turns; status None = pending, "ok", "failed"
    image_summary: Optional[str] = None
    summary_status: Optional[str] = None

    class Config:
        from_attributes = True

class MessageResponse(MessageBase):
    id: str
    session_id: str
    timestamp: datetime
    image_mime_type: Optional[str] = None
    image_size_bytes: Optional[int] = None
    kind: Optional[str] = None
    # Document metadata only; the extracted text itself is not sent to the browser
    document_name: Optional[str] = None
    document_mime_type: Optional[str] = None
    document_size_bytes: Optional[int] = None
    document_text_status: Optional[str] = None
    hint_total: Optional[int] = None
    hint_allow_answer: Optional[bool] = None
    # Every file on the message (the image_*/document_* fields above describe only the first of each)
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True

class CheckpointCreate(BaseModel):
    session_id: str
    message_id: str

class CheckpointResponse(BaseModel):
    id: str
    session_id: str
    message_id: str
    source: str
    summary_token_count: Optional[int] = None
    created_at: Optional[datetime] = None
    # Structured learning-state summary (parsed from summary_text)
    summary: dict = {}

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _parse_summary(cls, data):
        text = getattr(data, "summary_text", None)
        if text is not None and not isinstance(data, dict):
            try:
                summary = json.loads(text)
            except ValueError:
                summary = {"continuation_notes": text}
            return {
                "id": data.id, "session_id": data.session_id, "message_id": data.message_id,
                "source": data.source, "summary_token_count": data.summary_token_count,
                "created_at": data.created_at, "summary": summary if isinstance(summary, dict) else {},
            }
        return data

class AdminMessageResponse(MessageResponse):
    # The hint planner's assessment is shown to instructors only
    hint_assessment: Optional[dict] = None

    @field_validator("hint_assessment", mode="before")
    @classmethod
    def _parse_assessment(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v

class StudentDetailResponse(StudentResponse):
    sessions: List[SessionResponse]

    class Config:
        from_attributes = True
