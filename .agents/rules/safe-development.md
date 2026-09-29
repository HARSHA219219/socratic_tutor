---
description: Safe development practices and constraints for the Socratic Tutor project
---

# Safe Development Guidelines for Socratic Tutor

When acting on this repository, all AI agents must follow these safety constraints and repository conventions:

## 1. Data Integrity & Persistence
* **Do NOT delete, reset, or overwrite `backend/socratic.db`** unless the user explicitly requests a database wipe.
* Treat student session transcripts and conversation logs as stateful, production-style user data.
* Do NOT run destructive Alembic migrations or downgrade scripts without explicit instructions.

## 2. Secrets & Configuration
* `backend/.env` contains the active `OPENROUTER_API_KEY`. Never replace it with dummy or placeholder values, and never commit secrets into public repositories.
* Keep JWT secret configuration intact in `backend/app/core/config.py`.

## 3. Architecture & API Conventions
* **Async Database Access:** Maintain async SQLAlchemy 2.0 throughout FastAPI routes and services. Never introduce blocking synchronous database calls (`db.query()`).
* **Student Identity:** Preserve the passwordless `(name, roll_no)` identity pattern. Do not add password fields or complex auth schemas to the student model unless directed.
* **Separation of Workspaces:** Always execute Python commands within the `backend/` directory using its virtual environment (`venv`), and frontend commands within `frontend/` using `npm`.
