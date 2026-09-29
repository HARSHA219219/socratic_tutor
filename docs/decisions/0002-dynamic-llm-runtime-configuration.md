# ADR 0002: Dynamic Runtime LLM Configuration via Database

## Status
Accepted / Implemented

## Context
During instructional sessions or pedagogical testing, instructors need to refine the tutor's behavior (the Socratic system prompt) or switch between language models (e.g. `openai/gpt-4o-mini`, Claude, etc.) without restarting the backend service or triggering code deployments.

## Decision
System prompt and model name are stored dynamically in the database table `app_config`:
* Seeded automatically on FastAPI application startup (`@app.on_event("startup")`) if records do not exist.
* Accessible and mutable via authenticated instructor endpoints: `GET /api/admin/config` and `PUT /api/admin/config`.
* Queried dynamically in `backend/app/services/llm_service.py` on every user chat message.

## Consequences
* Changes take effect instantly for all subsequent student interactions without downtime.
* Configuration is persisted across backend restarts within the database.
* Introduces a lightweight database query prior to generating LLM responses (cached or directly read within the same async transaction).
