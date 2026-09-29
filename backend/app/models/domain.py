from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Boolean, Index, func as sa_func
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    roll_no = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=False)
    # NULL for legacy students who have not yet set a password (claimed their account)
    password_hash = Column(String, nullable=True)
    # Only a hash of the one-time recovery code is ever stored
    recovery_code_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Case-insensitive uniqueness: "Ravi" and "ravi" collide
        Index("ix_students_username_lower", sa_func.lower(username), unique=True),
    )

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    title = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Optional attached image: server-generated file name inside IMAGE_STORAGE_DIR
    image_key = Column(String, nullable=True)
    image_mime_type = Column(String, nullable=True)
    image_size_bytes = Column(Integer, nullable=True)
    # Optional attached document: server-generated file name inside DOCUMENT_STORAGE_DIR.
    # document_name is the sanitized original filename, for display/download only.
    document_key = Column(String, nullable=True)
    document_name = Column(String, nullable=True)
    document_mime_type = Column(String, nullable=True)
    document_size_bytes = Column(Integer, nullable=True)
    document_text = Column(Text, nullable=True)
    document_text_status = Column(String, nullable=True)  # "ok" | "truncated" | "image" (PDF read as page images)
    # NULL for a normal message; "hint-1".."hint-3" or "answer" for hint-ladder / direct-answer turns
    kind = Column(String, nullable=True)
    # Adaptive hint ladder: total hints planned for this question, whether the answer button
    # is offered, and the planner's assessment (JSON, instructors only)
    hint_total = Column(Integer, nullable=True)
    hint_allow_answer = Column(Boolean, nullable=True)
    hint_assessment = Column(Text, nullable=True)
    # All files attached to this message (the image_*/document_* columns above mirror the
    # first image / first document for backward compatibility)
    attachments = relationship(
        "MessageAttachment",
        order_by="MessageAttachment.position",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

class MessageAttachment(Base):
    """One uploaded file on a message. The file lives on disk; SQLite keeps only metadata."""
    __tablename__ = "message_attachments"

    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, ForeignKey("messages.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    kind = Column(String, nullable=False)  # "image" | "document"
    storage_key = Column(String, nullable=False)  # random file name in IMAGE_/DOCUMENT_STORAGE_DIR
    name = Column(String, nullable=True)  # sanitized original filename, display only
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    # Documents
    extracted_text = Column(Text, nullable=True)
    text_status = Column(String, nullable=True)  # "ok" | "truncated" | "image"
    # Images: description reused in later turns instead of re-sending the image
    image_summary = Column(Text, nullable=True)
    summary_status = Column(String, nullable=True)  # None (pending) | "ok" | "failed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationCheckpoint(Base):
    """Learning-state summary of a session through `message_id` (inclusive)."""
    __tablename__ = "conversation_checkpoints"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    message_id = Column(String, ForeignKey("messages.id"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)  # JSON learning-state summary
    summary_token_count = Column(Integer, nullable=True)
    source = Column(String, nullable=False, default="manual")  # "manual" | "automatic"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AppConfig(Base):
    __tablename__ = "app_config"

    config_key = Column(String, primary_key=True)
    config_value = Column(Text, nullable=False)
