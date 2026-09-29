# System Architecture: Socratic Tutor

This document details the architecture, component boundaries, data flows, and integrations of the Socratic Tutor system as implemented in the codebase.

---

## 1. High-Level Architecture Diagram

```
                             +-------------------------------+
                             |         Web Browser           |
                             |  +-------------------------+  |
                             |  |   React SPA (Vite/TS)   |  |
                             |  |  Student / Admin Views  |  |
                             |  +------------+------------+  |
                             +---------------|---------------+
                                             | HTTP / REST
                                             v
                             +-------------------------------+
                             |        FastAPI Backend        |
                             |  +-------------------------+  |
                             |  | Routers:                |  |
                             |  | - /api/students         |  |
                             |  | - /api/sessions         |  |
                             |  | - /api/chat             |  |
                             |  | - /api/admin            |  |
                             |  +------------+------------+  |
                             |  | Services & Security:    |  |
                             |  | - llm_service.py        |  |
                             |  | - security.py (JWT)     |  |
                             |  +----+---------------+----+  |
                             +-------|---------------|-------+
                                     |               |
                         SQLAlchemy  |               | AsyncOpenAI
                         (aiosqlite) |               | HTTP Client
                                     v               v
                        +--------------------+  +--------------------+
                        |  SQLite Database   |  | OpenRouter API     |
                        | (backend/socratic. |  | (LLM Provider)     |
                        |        db)         |  +--------------------+
                        +--------------------+
```

---

## 2. Component Responsibilities

### 2.1 Frontend (`frontend/src/`)
The frontend is a single-page application built with React 19, TypeScript, and Vite. It is divided into two logical sections:

1. **Student Workspace:**
   * `pages/StudentLogin.tsx`: Captures student name and roll number. Calls `POST /api/students/` to get or register the student entity, storing student metadata and forwarding to `/chat`.
   * `pages/StudentChat.tsx`: Two-column workspace. The left column lists previous sessions retrieved via `GET /api/sessions/student/{studentId}` and provides a button to create new sessions. The main pane displays message history (`GET /api/chat/session/{sessionId}`) and a submission input to dispatch user queries (`POST /api/chat/`).

2. **Instructor / Admin Workspace:**
   * `pages/AdminLogin.tsx`: Submits credentials via OAuth2 form data to `POST /api/admin/login` and stores the resulting JWT token in browser `localStorage`.
   * `components/AdminProtectedRoute.tsx`: Guards administrative routes, redirecting unauthenticated users to `/admin`.
   * `pages/AdminDashboard.tsx`: Allows instructors to inspect and modify runtime configuration (`LLM_MODEL` and `SYSTEM_PROMPT`).
   * `pages/StudentLogsPage.tsx`: Displays a table of all enrolled students with session counters and navigation to session details.
   * `pages/StudentSessionsPage.tsx`: Renders all sessions belonging to a specific student, allowing the instructor to review full conversation transcripts.
   * `components/DownloadLogsModal.tsx`: Provides export options for downloading collected student sessions and messages in CSV or XLSX format.

3. **API Service Clients (`frontend/src/services/`):**
   * `api.ts`: Houses Axios client methods for student, session, and chat operations using `import.meta.env.VITE_API_URL`.
   * `adminApi.ts`: Houses Axios calls for admin-authenticated operations, attaching the `Authorization: Bearer <token>` header from `localStorage`.

---

### 2.2 Backend (`backend/app/`)
The backend is an asynchronous FastAPI application organized into standard layered modules:

* **Entrypoint (`main.py`):**
  * Initializes FastAPI with global CORS middleware allowing all origins (`*`).
  * On startup, checks the `app_config` table and seeds default values for `LLM_MODEL` (`openai/gpt-4o-mini`) and `SYSTEM_PROMPT` if they do not already exist.
  * Mounts routers with designated path prefixes.

* **API Endpoints (`api/`):**
  * `student.py`: Handles student registration and retrieval based on roll number uniqueness.
  * `session.py`: Handles session creation and per-student session enumeration.
  * `chat.py`: Handles sending chat messages, saving conversation history, and querying the tutor response.
  * `admin.py`: Handles admin authentication (JWT issuance), configuration reads/updates, student and session log inspection, and data export.

* **Core & Security (`core/`):**
  * `config.py`: Loads environment configurations via `pydantic-settings` (`Settings`), defining database URL, JWT secret, algorithm, expiration, and default hashed admin credentials.
  * `security.py`: Implements password hashing verification (`bcrypt` via `passlib`) and JWT encoding/decoding (`python-jose`).

* **Database Layer (`db/` & `models/`):**
  * `db/database.py`: Instantiates `AsyncEngine` and `async_sessionmaker` (`AsyncSessionLocal`), alongside the `get_db` async generator dependency.
  * `models/domain.py`: Defines Declarative Base models:
    * `Student`: `id` (UUID string), `name`, `roll_no` (unique, indexed), `created_at`.
    * `Session`: `id` (UUID string), `student_id` (ForeignKey `students.id`), `started_at`, `ended_at`.
    * `Message`: `id` (UUID string), `session_id` (ForeignKey `sessions.id`), `role` (`user` or `assistant`), `content` (Text), `timestamp`.
    * `AppConfig`: `config_key` (primary key string), `config_value` (Text).

* **AI Service Layer (`services/llm_service.py`):**
  * Manages interaction with OpenRouter via `openai.AsyncOpenAI`.
  * Assembles prompt messages: dynamically fetches `SYSTEM_PROMPT` and `LLM_MODEL` from the database, loads chronological message history for the active session, appends the new student message, and queries the model.

---

## 3. Core Data Flows

### 3.1 Student Identification and Session Creation
```
Student Browser                 FastAPI Router                  Database
      |                               |                             |
      |-- POST /api/students/ ------->|                             |
      |   {name, roll_no}             |-- SELECT by roll_no ------->|
      |                               |<-- Return student / null ---|
      |                               |                             |
      |                               |-- (If new) INSERT Student ->|
      |<-- Return Student Object -----|                             |
      |                               |                             |
      |-- POST /api/sessions/ ------->|                             |
      |   {student_id}                |-- INSERT Session ---------->|
      |<-- Return Session Object -----|                             |
```

### 3.2 Chat Interaction and Socratic Response
```
Student Browser            FastAPI /api/chat        llm_service.py        OpenRouter API         Database
      |                           |                       |                      |                  |
      |-- POST /api/chat/ ------->|                       |                      |                  |
      |   {session_id, message}   |-- Verify session ---------------------------------------------->|
      |                           |-- INSERT user Message ----------------------------------------->|
      |                           |                       |                      |                  |
      |                           |-- generate_tutor_ ---->                      |                  |
      |                           |   response()          |-- SELECT Config (prompt/model) -------->|
      |                           |                       |-- SELECT History (messages) ----------->|
      |                           |                       |                      |                  |
      |                           |                       |-- POST chat/ -------->                  |
      |                           |                       |   completions        |                  |
      |                           |                       |<-- LLM response -----|                  |
      |                           |<-- Return reply ------|                                         |
      |                           |                                                                 |
      |                           |-- INSERT assistant Message ------------------------------------>|
      |<-- ChatResponse ----------|
```

### 3.3 Admin Live Configuration Update
```
Instructor Browser          FastAPI /api/admin/config             Database
      |                                  |                           |
      |-- PUT /api/admin/config -------->|                           |
      |   (Bearer JWT + payload)         |-- Verify JWT Token        |
      |                                  |-- UPSERT LLM_MODEL ------>|
      |                                  |-- UPSERT SYSTEM_PROMPT -->|
      |<-- ConfigResponse ---------------|                           |
```
*Subsequent calls to `/api/chat/` immediately use the newly updated prompt and model without server restarts.*

---

## 4. Integration Points

| Integration | Mechanism | Target / Details |
|---|---|---|
| Frontend to Backend | REST over HTTP | Axios clients pointing to FastAPI endpoints (`http://127.0.0.1:8000/api`) |
| Backend to LLM | OpenRouter REST API | `openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1")` using `OPENROUTER_API_KEY` |
| Backend to Database | Async SQLAlchemy 2.0 | Async connection pool via `aiosqlite` targeting local `socratic.db` |
| Containerized DB (Optional) | PostgreSQL 15 | Defined in `docker-compose.yml` (`5432:5432`), ready for production switch |
| Admin Authentication | JWT (HS256) | Encoded and decoded using `python-jose` with shared secret from `Settings` |
