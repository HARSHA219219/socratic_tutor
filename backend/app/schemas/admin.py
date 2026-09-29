from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime
from .domain import StudentResponse, SessionResponse, MessageResponse

class AdminLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class AppConfigUpdate(BaseModel):
    model: str
    system_prompt: str
    vision_model: Optional[str] = None

class ConfigResponse(BaseModel):
    model: str
    system_prompt: str
    vision_model: str = ""


def _validate_new_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password is too long (max 72 bytes)")
    return v

class AdminRecoveryVerify(BaseModel):
    username: str
    recovery_code: str

class AdminPasswordReset(BaseModel):
    reset_token: str
    new_password: str

    _p = field_validator("new_password")(_validate_new_password)

class AdminChangePassword(BaseModel):
    current_password: str
    new_password: str

    _p = field_validator("new_password")(_validate_new_password)

class AdminCurrentPassword(BaseModel):
    current_password: str

class AdminResetResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    recovery_code: str

class RecoveryCodeResponse(BaseModel):
    recovery_code: str

class SecurityStatus(BaseModel):
    username: str
    has_recovery_code: bool
    password_changed: bool
