from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.domain import Student
from app.schemas.domain import (
    StudentSignup, StudentLoginRequest, StudentResponse, StudentAuthResponse,
    RecoveryVerifyRequest, RecoveryVerifyResponse, PasswordResetRequest,
)
from app.core.security import (
    get_password_hash, verify_password, create_student_token, get_current_student_id,
    generate_recovery_code, hash_recovery_code, verify_recovery_code,
    create_reset_token, decode_reset_token, recovery_fingerprint,
    login_limiter, recovery_limiter,
)

router = APIRouter()

USERNAME_TAKEN = "That username is already taken. Please choose another."
BAD_LOGIN = "Invalid username or password."
BAD_RECOVERY = "Invalid username or recovery code."

async def _find_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(Student).where(func.lower(Student.username) == username.strip().lower()))
    return result.scalars().first()

def _client_key(request: Request) -> str:
    return f"ip:{request.client.host if request.client else 'unknown'}"

def _issue_recovery_code(student: Student) -> str:
    code = generate_recovery_code()
    student.recovery_code_hash = hash_recovery_code(code)
    return code

@router.post("/signup", response_model=StudentAuthResponse)
async def signup(data: StudentSignup, db: AsyncSession = Depends(get_db)):
    owner = await _find_by_username(db, data.username)

    result = await db.execute(select(Student).where(Student.roll_no == data.roll_no))
    existing = result.scalars().first()

    if existing:
        if existing.password_hash:
            raise HTTPException(status_code=409, detail="An account with this roll number already exists. Please sign in.")
        if existing.name != data.name:
            raise HTTPException(status_code=400, detail="Roll number exists with a different name.")
        # Legacy student (created before accounts existed): claim the record so chat history is kept
        if owner and owner.id != existing.id:
            raise HTTPException(status_code=409, detail=USERNAME_TAKEN)
        student = existing
        student.username = data.username
    else:
        if owner:
            raise HTTPException(status_code=409, detail=USERNAME_TAKEN)
        student = Student(name=data.name, roll_no=data.roll_no, username=data.username)
        db.add(student)

    student.password_hash = get_password_hash(data.password)
    code = _issue_recovery_code(student)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent signup won the race on the case-insensitive unique index
        await db.rollback()
        raise HTTPException(status_code=409, detail=USERNAME_TAKEN)
    await db.refresh(student)
    return StudentAuthResponse(
        access_token=create_student_token(student.id),
        student=StudentResponse.model_validate(student),
        recovery_code=code,
    )

@router.post("/login", response_model=StudentAuthResponse)
async def login(data: StudentLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    keys = (f"user:{data.username.strip().lower()}", _client_key(request))
    login_limiter.check(*keys)
    student = await _find_by_username(db, data.username)
    if not student or not student.password_hash or not verify_password(data.password, student.password_hash):
        login_limiter.fail(*keys)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=BAD_LOGIN)
    login_limiter.reset(keys[0])
    return StudentAuthResponse(
        access_token=create_student_token(student.id),
        student=StudentResponse.model_validate(student),
    )

@router.get("/me", response_model=StudentResponse)
async def me(student_id: str = Depends(get_current_student_id), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=401, detail="Please sign in again")
    return student

@router.post("/recover/verify", response_model=RecoveryVerifyResponse)
async def recover_verify(data: RecoveryVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    keys = (f"user:{data.username.strip().lower()}", _client_key(request))
    recovery_limiter.check(*keys)
    student = await _find_by_username(db, data.username)
    code_hash = student.recovery_code_hash if student else None
    # Same message and similar timing whether or not the username exists
    if not verify_recovery_code(data.recovery_code, code_hash):
        recovery_limiter.fail(*keys)
        raise HTTPException(status_code=400, detail=BAD_RECOVERY)
    recovery_limiter.reset(keys[0])
    return RecoveryVerifyResponse(reset_token=create_reset_token(student.id, code_hash))

@router.post("/recover/reset", response_model=StudentAuthResponse)
async def recover_reset(data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    expired = HTTPException(status_code=400, detail="This reset request has expired. Please start again.")
    payload = decode_reset_token(data.reset_token)
    if not payload:
        raise expired
    student = await db.get(Student, payload.get("sub"))
    # The token is bound to the recovery code it was issued for, so it only works once
    if not student or not student.recovery_code_hash or recovery_fingerprint(student.recovery_code_hash) != payload.get("rcf"):
        raise expired
    student.password_hash = get_password_hash(data.new_password)
    code = _issue_recovery_code(student)  # old code is invalidated
    await db.commit()
    await db.refresh(student)
    return StudentAuthResponse(
        access_token=create_student_token(student.id),
        student=StudentResponse.model_validate(student),
        recovery_code=code,
    )
