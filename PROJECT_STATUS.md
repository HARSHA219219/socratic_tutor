# Project Status: Socratic Tutor

*Last Updated: 2026-09-15*
*Document Status: Verified against repository code and live runtime state.*

---

## 1. Project Purpose

The Socratic Tutor is a web-based educational system designed to provide guided, question-driven tutoring dialogues to students using a single Large Language Model (LLM) configured via a Socratic Tutor prompt. 

The application enables students to engage in persistent tutoring sessions identified solely by their name and student roll number, while instructors/administrators have a protected dashboard to monitor student sessions, view full conversation transcripts, update model parameters and system prompts live, and export logs.

---

## 2. Current Architecture (High Level)

* **Client Layer:** Single-page application built with React 19, TypeScript, Vite, and Tailwind CSS v4. Consists of a student chat interface and an authenticated administrator portal.
* **API Layer:** FastAPI (Python) asynchronous application providing REST endpoints for student management, session tracking, Socratic chat generation, and admin auditing.
* **AI Integration:** Centralized LLM client communicating with OpenRouter (`https://openrouter.ai/api/v1`) using the OpenAI asynchronous Python SDK. Model selection and system prompt are fetched dynamically from the database on each invocation.
* **Storage Layer:** SQLAlchemy 2.0 Async ORM. Development is currently running on SQLite (`backend/socratic.db`) via `aiosqlite`. A Docker Compose configuration (`docker-compose.yml`) defines a PostgreSQL 15 container for production-oriented environments.

---

## 3. Completed and Verified Components

The following components are implemented and functional based on existing codebase inspection:

### Backend (`backend/app/`)
* **Student Management (`api/student.py`):**
  * `POST /api/students/`: Gets an existing student by roll number or creates a new record. Enforces consistent name pairing for existing roll numbers.
* **Session Management (`api/session.py`):**
  * `POST /api/sessions/`: Creates a new session tied to a student.
  * `GET /api/sessions/student/{student_id}`: Lists all sessions for a specific student sorted in descending order of start time.
* **Chat Service (`api/chat.py` & `services/llm_service.py`):**
  * `POST /api/chat/`: Accepts a message, persists the user message to SQLite, compiles historical conversation context, queries OpenRouter, persists the assistant reply, and returns the response.
  * `GET /api/chat/session/{session_id}`: Retrieves chronological message history for a given session.
  * `startup` event (`main.py`): Automatically seeds default `AppConfig` records (`LLM_MODEL: "openai/gpt-4o-mini"` and `SYSTEM_PROMPT`) if absent.
* **Admin Authentication & Management (`api/admin.py`):**
  * `POST /api/admin/login`: Issues OAuth2 JWT bearer token upon verifying hashed administrator credentials.
  * `GET /api/admin/config`: Retrieves active model name and system prompt.
  * `PUT /api/admin/config`: Dynamically updates model and system prompt in the database without requiring server restart.
  * `GET /api/admin/students`: Lists all registered students.
  * `GET /api/admin/students/{student_id}`: Returns student details with their associated sessions.
  * `GET /api/admin/students/{student_id}/sessions/{session_id}`: Returns messages for a specific student session.

### Frontend (`frontend/src/`)
* **Student Experience:**
  * `StudentLogin.tsx`: Roll number and student name intake screen; creates or retrieves student record and redirects to chat.
  * `StudentChat.tsx`: Two-pane interface featuring session creation, session history list, active chat message display, and question input.
* **Admin Experience:**
  * `AdminLogin.tsx`: Admin login form saving JWT to `localStorage`.
  * `AdminDashboard.tsx`: Controls for editing system prompt and model identifier.
  * `StudentLogsPage.tsx`: Table listing students with navigation to session logs and export modal.
  * `StudentSessionsPage.tsx`: Detailed view of sessions and message transcripts for an individual student.
  * `DownloadLogsModal.tsx`: Interface for exporting logs in XLSX or CSV format.
  * `AdminProtectedRoute.tsx`: Route guard checking for `admin_token` before rendering administrative views.

---

## 4. Current Execution State (Confirmed Facts)

* Both frontend and backend development servers are actively executing in the environment:
  * Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (PID active)
  * Frontend: Vite dev server running `npm run dev` (PID active)
* The SQLite database file `backend/socratic.db` is present and holds active data.
* Root test script `test-admin.ps1` verifies the admin authentication and configuration update pipeline.

---

## 5. Known Issues and Inconsistencies (Documented for Future Sessions)

> [!WARNING]
> These issues exist in the current codebase. Under safety constraints, they have been left untouched for future resolution.

1. **Missing `io` Import in Admin Export Route (`backend/app/api/admin.py`):**
   * Endpoint `GET /api/admin/export/all` utilizes `io.BytesIO()` (line 122) and `io.StringIO()` (line 183), but `import io` is not included in the file imports. Calling this endpoint will result in an unhandled `NameError`.
2. **Missing ORM Relationship on Message (`backend/app/api/admin.py`):**
   * In `admin.py` line 114, `getattr(m.session, 'student_id', '')` attempts to traverse `m.session`. However, `Message` in `backend/app/models/domain.py` does not define a SQLAlchemy `relationship` for `session`, so this attribute access will not resolve student ID directly from `m`.
3. **[RESOLVED] Standardized Frontend API Base URL:**
   * Replaced hardcoded `http://127.0.0.1:8000/api` instances across `adminApi.ts`, `AdminLogin.tsx`, `AdminDashboard.tsx`, and `DownloadLogsModal.tsx` with a centralized, normalized `API_BASE_URL` exported from `api.ts`.
4. **Discrepancy Between Local Database and Docker Specification:**
   * `backend/app/core/config.py` defaults to SQLite (`sqlite+aiosqlite:///./socratic.db`), whereas `initial_system_design.md` and `docker-compose.yml` designate PostgreSQL. Local development currently operates purely on SQLite.

---

## 6. Pending / Potential Next Steps

*(Determined strictly from code state and project specification)*

1. **Bugfixes:** Resolve the `import io` and ORM relationship issues in `backend/app/api/admin.py` when safe to do so.
2. **Configuration Alignment:** Consolidate frontend API base URLs to use environment variables consistently.
3. **Database Environment Support:** Add optional PostgreSQL connection string support via environment variable in `backend/app/core/config.py` so the application can alternate seamlessly between SQLite and PostgreSQL in Docker.
4. **Markdown Rendering in Student Chat:** Render assistant responses with markdown/math support if formatted Socratic questions require LaTeX or structured text.
5. **Formal Automated Testing:** Set up automated tests (e.g. `pytest` for backend API routes and `vitest` for frontend components) to augment the existing manual scripts (`test.py`, `test-admin.ps1`).
