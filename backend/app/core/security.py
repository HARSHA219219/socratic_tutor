from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
import time
from collections import defaultdict, deque
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def _decode(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def _admin_from_payload(payload: dict) -> Optional[str]:
    username = payload.get("sub")
    if payload.get("typ") or username is None or username != settings.ADMIN_USERNAME:
        return None
    return username

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = _admin_from_payload(_decode(token))
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# ----- Student auth -----

def create_student_token(student_id: str) -> str:
    return create_access_token(
        {"sub": student_id, "typ": "student"},
        timedelta(minutes=settings.STUDENT_TOKEN_EXPIRE_MINUTES),
    )

async def get_current_student_id(token: str = Depends(oauth2_scheme)) -> str:
    """Returns the student id from a student JWT (existence is checked by callers)."""
    try:
        payload = _decode(token)
    except JWTError:
        payload = {}
    if payload.get("typ") != "student" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload["sub"]

async def get_current_principal(token: str = Depends(oauth2_scheme)) -> dict:
    """Accepts either an admin or a student token (used for image retrieval)."""
    try:
        payload = _decode(token)
    except JWTError:
        payload = {}
    if payload.get("typ") == "student" and payload.get("sub"):
        return {"kind": "student", "id": payload["sub"]}
    if _admin_from_payload(payload):
        return {"kind": "admin", "id": payload["sub"]}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

# ----- Recovery codes -----

_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I

def generate_recovery_code() -> str:
    """~100 bits of entropy, formatted XXXXX-XXXXX-XXXXX-XXXXX."""
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(20))
    return "-".join(raw[i:i + 5] for i in range(0, 20, 5))

def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())

def hash_recovery_code(code: str) -> str:
    return pwd_context.hash(normalize_recovery_code(code))

def verify_recovery_code(code: str, code_hash: Optional[str]) -> bool:
    if not code_hash:
        # Burn comparable time so a missing account/code is not distinguishable
        pwd_context.verify("x", _DUMMY_HASH)
        return False
    return pwd_context.verify(normalize_recovery_code(code), code_hash)

_DUMMY_HASH = pwd_context.hash("not-a-real-secret")

def recovery_fingerprint(code_hash: str) -> str:
    """Binds a reset token to the current recovery code so it is single-use."""
    return hashlib.sha256(code_hash.encode()).hexdigest()[:16]

def create_reset_token(subject: str, code_hash: str, typ: str = "reset") -> str:
    return create_access_token(
        {"sub": subject, "typ": typ, "rcf": recovery_fingerprint(code_hash)},
        timedelta(minutes=10),
    )

def decode_reset_token(token: str, typ: str = "reset") -> Optional[dict]:
    try:
        payload = _decode(token)
    except JWTError:
        return None
    return payload if payload.get("typ") == typ else None

# ----- In-memory attempt limiter (per process) -----

class AttemptLimiter:
    def __init__(self):
        self._failures: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str) -> deque:
        q = self._failures[key]
        cutoff = time.monotonic() - settings.AUTH_WINDOW_SECONDS
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def check(self, *keys: str) -> None:
        for key in keys:
            # Shared keys (e.g. a classroom IP) get a looser limit than per-username keys
            limit = settings.AUTH_MAX_FAILURES * (4 if key.startswith("ip:") else 1)
            if len(self._prune(key)) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait a few minutes and try again.",
                )

    def fail(self, *keys: str) -> None:
        for key in keys:
            self._failures[key].append(time.monotonic())

    def reset(self, *keys: str) -> None:
        for key in keys:
            self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()

login_limiter = AttemptLimiter()
recovery_limiter = AttemptLimiter()
admin_limiter = AttemptLimiter()
