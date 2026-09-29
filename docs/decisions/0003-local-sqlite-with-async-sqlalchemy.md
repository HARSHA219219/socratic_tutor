# ADR 0003: Local SQLite Storage with Async SQLAlchemy 2.0

## Status
Accepted / Implemented

## Context
The production specification calls for PostgreSQL (`docker-compose.yml`), but local developer workflows require quick setup without mandatory Docker container orchestration.

## Decision
Use SQLAlchemy 2.0 async engine with `aiosqlite` (`sqlite+aiosqlite:///./socratic.db`) as the default local development database:
* All database interactions use modern async SQLAlchemy patterns (`select()`, `db.execute()`, `async_sessionmaker`).
* Table definitions in `backend/app/models/domain.py` use standard relational constructs compatible with both SQLite and PostgreSQL.
* Database initialization and schema changes are tracked with Alembic (`backend/alembic/`).

## Consequences
* Immediate developer onboarding without requiring external PostgreSQL services to be launched.
* Seamless upgrade path to PostgreSQL by altering `DATABASE_URL` in `Settings` or `.env` when deploying in containerized environments.
