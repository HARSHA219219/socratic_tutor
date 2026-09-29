from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine
from app.core.config import settings

app = FastAPI(title="Socratic Tutor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.models.domain import AppConfig
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal

@app.on_event("startup")
async def startup():
    async with AsyncSessionLocal() as db:
        # Seed default model if not exists
        result = await db.execute(select(AppConfig).where(AppConfig.config_key == "LLM_MODEL"))
        if not result.scalars().first():
            db.add(AppConfig(config_key="LLM_MODEL", config_value="openai/gpt-4o-mini"))
        
        # Seed default prompt if not exists
        result = await db.execute(select(AppConfig).where(AppConfig.config_key == "SYSTEM_PROMPT"))
        if not result.scalars().first():
            db.add(AppConfig(config_key="SYSTEM_PROMPT", config_value="You are a helpful Socratic Tutor. Ask questions to help the student learn, rather than giving direct answers."))
        
        # Seed vision model (used when a message includes an image) if not exists
        result = await db.execute(select(AppConfig).where(AppConfig.config_key == "VISION_MODEL"))
        if not result.scalars().first():
            db.add(AppConfig(config_key="VISION_MODEL", config_value="openai/gpt-4o-mini"))
        
        await db.commit()


from app.api import admin, student, session, chat, images, documents, checkpoints, attachments
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

app.include_router(student.router, prefix="/api/students", tags=["students"])
app.include_router(session.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(checkpoints.router, prefix="/api/checkpoints", tags=["checkpoints"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["attachments"])

@app.get("/")
def read_root():
    return {"status": "ok"}
