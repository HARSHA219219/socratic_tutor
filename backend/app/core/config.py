from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "DATABASE_URL=sqlite+aiosqlite:////var/data/my_new_database.db"
    OPENROUTER_API_KEY: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = "$2b$12$KRwj2uDlhJDxkne/jOsQGe7AP61Fc3xeNzs5OrbgfQJWAPv3KxcNi" # Default: "admin123"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    STUDENT_TOKEN_EXPIRE_MINUTES: int = 720

    # Image uploads: files live on disk, only references/metadata go in SQLite
    IMAGE_STORAGE_DIR: str = "./uploads/images"
    MAX_IMAGE_BYTES: int = 5 * 1024 * 1024
    MAX_HISTORY_IMAGES: int = 3

    # Document uploads (PDF/DOCX/TXT): files on disk, metadata + extracted text in SQLite
    DOCUMENT_STORAGE_DIR: str = "./uploads/documents"
    MAX_DOCUMENT_BYTES: int = 10 * 1024 * 1024
    # Extracted text is cut to this many characters before it is stored and sent to the LLM
    MAX_DOCUMENT_TEXT_CHARS: int = 20000
    # PDFs without a text layer (scans / outlined text): pages rendered as images for the vision model
    MAX_PDF_IMAGE_PAGES: int = 4

    # Multiple attachments per message
    MAX_ATTACHMENTS_PER_MESSAGE: int = 5
    MAX_TOTAL_ATTACHMENT_BYTES: int = 20 * 1024 * 1024
    # One message's attachment content may use at most this % of CONTEXT_TOKEN_BUDGET
    ATTACHMENT_CONTEXT_PERCENT: int = 45

    # Image descriptions reused in later turns instead of re-sending the image
    IMAGE_SUMMARY_ENABLED: bool = True
    IMAGE_SUMMARY_MAX_TOKENS: int = 300

    # Conversation checkpoints / automatic window summary
    SUMMARY_ENABLED: bool = True
    # Create an automatic checkpoint when the prompt reaches this % of CONTEXT_TOKEN_BUDGET
    SUMMARY_WARNING_PERCENT: int = 80
    # Max output tokens for one checkpoint summary
    SUMMARY_MAX_TOKENS: int = 1500
    # Application prompt budget (deliberately far below any provider's maximum context)
    CONTEXT_TOKEN_BUDGET: int = 16000

    # Brute-force limits for student login / password recovery
    AUTH_MAX_FAILURES: int = 5
    AUTH_WINDOW_SECONDS: int = 900

    # Comma-separated frontend URLs allowed to call the API, e.g. "https://tutor.onrender.com".
    # "*" (default) allows any origin, which is fine for local development.
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins or ["*"]

settings = Settings()
