# Agent Guidelines for Socratic Tutor

This document provides operational guidelines, technical context, and safe working practices for AI coding agents operating within this repository.

---

## 1. Repository Overview

The Socratic Tutor repository is a full-stack educational web application that pairs students with an AI tutor using the Socratic method, while giving instructors an administrative dashboard to manage configuration and inspect student chat logs.

### Tech Stack
* **Backend:**
  * Python 3.11+ with FastAPI
  * Async SQLAlchemy 2.0 ORM with `aiosqlite` (SQLite) for local development
  * Pydantic v2 & `pydantic-settings`
  * `openai` Python SDK (targeting OpenRouter API endpoint)
  * `python-jose` (JWT) & `bcrypt` / `passlib` for admin authentication
  * `openpyxl` & Python `csv` for data export
* **Frontend:**
  * React 19 (`react`, `react-dom`) with TypeScript
  * Vite 8 build tool
  * Tailwind CSS v4 (`@tailwindcss/postcss`)
  * `react-router-dom` v7
  * `axios` for REST API communication
  * `lucide-react` for UI icons
* **Infrastructure / Data:**
  * SQLite database (`backend/socratic.db`) used for active local execution
  * `docker-compose.yml` defining PostgreSQL 15 container service for production/containerized setups
  * Alembic migration setup in `backend/alembic/`

---

## 2. Repository Layout

```text
Socratic_tutor/
├── AGENTS.md                   # This file (instructions for AI agents)
├── PROJECT_STATUS.md           # Snapshot of current project status and known issues
├── docker-compose.yml          # Postgres 15 alpine container definition
├── initial_system_design.md    # Initial specification document
├── package.json                # Root package.json
├── test-admin.ps1              # PowerShell test script for admin authentication/config
├── .agents/
│   └── rules/                  # Workspace-specific agent rules
├── backend/
│   ├── alembic/                # Database migrations
│   ├── alembic.ini             # Alembic configuration
│   ├── requirements.txt        # Python dependency manifest
│   ├── socratic.db             # Active SQLite database file
│   ├── test.py                 # Smoke test script for student/session/chat endpoints
│   └── app/
│       ├── main.py             # FastAPI entrypoint, CORS, startup config seeding, routers
│       ├── dependencies.py     # Shared FastAPI dependencies (get_db)
│       ├── api/                # Route handlers (admin, student, session, chat)
│       ├── core/               # Configuration (Settings) and security helpers (JWT/bcrypt)
│       ├── db/                 # Async SQLAlchemy engine and sessionmaker
│       ├── models/             # SQLAlchemy ORM models (Student, Session, Message, AppConfig)
│       ├── schemas/            # Pydantic validation schemas
│       └── services/           # Business logic & external services (llm_service.py)
├── docs/
│   ├── architecture.md         # System architecture and data flow documentation
│   └── decisions/              # Architectural Decision Records (ADRs)
└── frontend/
    ├── index.html              # HTML entrypoint
    ├── vite.config.ts          # Vite configuration
    ├── tsconfig.json           # TypeScript configuration
    ├── package.json            # Frontend dependency manifest & scripts
    └── src/
        ├── App.tsx             # React router configuration
        ├── main.tsx            # React application mount
        ├── index.css / App.css # Global styles
        ├── components/         # Reusable UI components & route guards
        ├── pages/              # Page components (StudentLogin, StudentChat, AdminLogin, AdminDashboard, etc.)
        ├── services/           # Axios API clients (api.ts, adminApi.ts)
        └── types/              # TypeScript interfaces and data models
```

---

## 3. Development and Testing Workflows

### Active Processes Notice
The user may already have servers running in background terminals:
* Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (working directory: `backend`)
* Frontend: `npm run dev` (working directory: `frontend`)
**Check before attempting to bind to ports 8000 or 5173.**

### Backend Commands (Always run from `backend/`)
* **Activate Virtual Environment:**
  * Windows PowerShell: `.\venv\Scripts\Activate.ps1`
  * Windows CMD: `.\venv\Scripts\activate.bat`
* **Install Dependencies:**
  `pip install -r requirements.txt`
* **Run Server Locally:**
  `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
* **Run Smoke Test:**
  `python test.py`

### Frontend Commands (Always run from `frontend/`)
* **Install Dependencies:**
  `npm install`
* **Run Dev Server:**
  `npm run dev`
* **Type-check & Build:**
  `npm run build`
* **Lint:**
  `npm run lint`

### Root Scripts
* **PowerShell Admin API Test:**
  `powershell -ExecutionPolicy Bypass -File .\test-admin.ps1`

---

## 4. Key Conventions and Architecture Rules

1. **Async Database Access:**
   * All database queries in FastAPI routes and services MUST use async SQLAlchemy 2.0 patterns:
     `await db.execute(select(...))` and `result.scalars().all()` / `.first()`.
   * Never introduce blocking synchronous database calls into route handlers.

2. **Student Identity Model (Strict Convention):**
   * Students sign up with `name`, `roll_no`, a **username** (unique, case-insensitive via the `lower(username)` index) and a **password** (bcrypt hash). No email.
   * Signup issues a one-time **recovery code**; only its bcrypt hash is stored. Password reset requires username + recovery code (`/api/students/recover/verify` then `/recover/reset`), which rotates the code. Never allow a reset by username alone.
   * Roll number stays unique. Legacy students (created before accounts, `password_hash IS NULL`) claim their record by signing up with the same name + roll number.
   * Student endpoints (sessions, chat, images) require a student JWT (`typ: "student"`), stored in `localStorage['student_token']`.
   * Chat images are stored on disk in `IMAGE_STORAGE_DIR` (default `backend/uploads/images`); SQLite only stores `image_key`/mime/size on `messages`.
   * Chat documents (PDF/DOCX/TXT, `POST /api/chat/document`) are stored in `DOCUMENT_STORAGE_DIR` (default `backend/uploads/documents`); SQLite stores `document_key`, sanitized name, mime, size, extracted text (capped at `MAX_DOCUMENT_TEXT_CHARS`) and status. Downloads go through the authenticated `GET /api/documents/{message_id}`.
   * A message can carry several files (`POST /api/chat/attachments` and `/api/chat/stream/attachments`, field `files`). Each file is a row in `message_attachments` (download: `GET /api/attachments/{id}`); the legacy `image_*`/`document_*` message columns mirror only the first image/document. Limits: `MAX_ATTACHMENTS_PER_MESSAGE`, `MAX_TOTAL_ATTACHMENT_BYTES`, and `ATTACHMENT_CONTEXT_PERCENT` of `CONTEXT_TOKEN_BUDGET` (rejected, never silently dropped). After the tutor sees an image, a background task stores `image_summary`; later prompts send that description instead of the image unless the student asks to re-check it or no description exists.
   * Conversation checkpoints (`/api/checkpoints`, table `conversation_checkpoints`) store a JSON learning-state summary through a message. Continuing creates a new session whose first message is `role="system"`, `kind="checkpoint_context"`. Before each tutor call, `prepare_tutor_prompt` in `llm_service.py` swaps old turns for the latest checkpoint once the prompt reaches `SUMMARY_WARNING_PERCENT` of `CONTEXT_TOKEN_BUDGET` (never dropping the latest student message).

3. **Admin Authentication:**
   * Uses OAuth2 password flow (`/api/admin/login`) returning a bearer JWT.
   * Admin credentials and JWT secret are configured in `backend/app/core/config.py` and `.env`.
   * Frontend stores the token in `localStorage.getItem('admin_token')`.

4. **Dynamic LLM Configuration:**
   * System prompt and model name are stored in the database table `app_config` (`LLM_MODEL`, `SYSTEM_PROMPT`).
   * The admin can update these live at runtime without restarting the server via `/api/admin/config`.
   * LLM calls route through `backend/app/services/llm_service.py` to OpenRouter using `openai.AsyncOpenAI`.

---

## 5. Safe Working Practices for AI Agents

* **Do NOT delete or overwrite `backend/socratic.db`** unless the user explicitly commands a database reset. Active session data and tutor configurations reside here.
* **Do NOT execute uncontrolled database migrations** without reviewing existing tables.
* **Preserve Environment Files:** `backend/.env` holds sensitive keys (e.g. `OPENROUTER_API_KEY`). Never expose keys or overwrite `.env` with dummy values.
* **Preserve Working Code:** When modifying code, keep changes minimal, localized, and well-tested. Do not reformat unrelated files or apply sweeping refactors.
* **Check Running Ports:** Verify if Uvicorn (8000) or Vite (5173) are active before attempting to run new server instances.
