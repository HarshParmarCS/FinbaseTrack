# FinTasks

A lightweight project management platform inspired by Jira, Linear and Trello. Built for the Finbase Full Stack Engineer assignment.

> **Status: milestones M0 (documentation) and M1 (backend foundation) complete.** The backend serves `GET /api/v1/health`; authentication, projects and tasks are not implemented yet. Sections marked *(planned)* describe the target state. See `docs/implementation-roadmap.md`. Backend setup: `backend/README.md`.

## Overview

Users register and log in, create projects, add registered users as project members, create and assign tasks, move tasks through `todo`, `in_progress` and `completed`, search and filter tasks, and view dashboard statistics and an activity timeline.

Authorization is a **centralized Policy-Based Access Control (PBAC)** engine with JSON-configurable policies and default-deny behavior. **RBAC is deliberately not used.**

## Technology stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Alembic, Pydantic, PyJWT, Argon2, pytest |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form, Zod, dnd-kit, Vitest, Playwright |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Architecture at a glance

Backend layers: **router -> (authorization dependency) -> service -> repository -> database**. Routers handle HTTP only. Services hold business rules. Repositories hold queries. All access decisions happen in the `authorization/` module. The browser talks to a single origin; Next.js proxies `/api/*` to the backend. Details: `.kiro/steering/architecture.md`.

## Documentation index

| Document | Purpose |
|---|---|
| `docs/requirements.md` | Requirements, assumptions, out of scope, acceptance checklist |
| `docs/database-design.md` | Schema, constraints, indexes, migration plan |
| `docs/api-contract.md` | REST endpoints, schemas, envelopes, error codes |
| `docs/authorization-design.md` | PBAC engine, policies, conditions, test matrix |
| `docs/implementation-roadmap.md` | Milestones M0 to M14 and acceptance criteria |
| `.kiro/steering/product.md` | Product definition and business rules |
| `.kiro/steering/architecture.md` | Approved architecture and decisions |
| `.kiro/steering/coding-standards.md` | Coding standards |
| `.kiro/steering/workflow.md` | Development process and rules |
| `docs/Full_Stack_Engineer_Assignment.pdf` | Original assignment |

## Setup *(planned, available from M1 onward)*

```bash
cp .env.example .env          # set POSTGRES_PASSWORD (openssl rand -hex 16)
podman compose up -d db       # database now (docker compose works too); whole stack with `up --build` after M13
```

Backend local development (available now; the database runs in a container, the API runs locally; full steps in `backend/README.md`):

```bash
# Backend (from backend/)
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt      # or: python3.12 -m venv .venv && pip install -r requirements-dev.txt
cp .env.example .env                        # set DATABASE_URL and TEST_DATABASE_URL (port 5433)
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (from frontend/)
pnpm install
pnpm dev
```

URLs once running: frontend `http://localhost:3000`, API docs `http://localhost:8000/docs`.

## Environment variables

All variables are listed with placeholders in `.env.example`. Secrets are never committed. In production the backend refuses to start with the placeholder `JWT_SECRET_KEY`.

## API documentation

Swagger UI at `/docs` and the exported schema `docs/openapi.json` *(planned, M8)*. The human-readable contract is `docs/api-contract.md`.

## Assumptions and trade-offs

Full list: `docs/requirements.md` (Assumptions) and the decision table in `.kiro/steering/architecture.md`. Key points:

- The project owner is automatically a member and cannot be removed. Only owners manage members.
- Task update is limited to the creator or the assignee (still members). Ownership alone does not grant update rights.
- A task can be completed only with an assignee and all required fields (title, description, assignee, due date).
- Non-members get 404, not 403, so project existence is not leaked.
- Hard deletes with audit history kept without foreign keys.
- Sync SQLAlchemy for simplicity. No frontend mock layer. No soft delete.

## Testing *(planned)*

```bash
cd backend && pytest               # runs against PostgreSQL via TEST_DATABASE_URL
cd frontend && pnpm test           # Vitest
```

## Development process

Milestone by milestone, with tests at every step and Conventional Commits. See `.kiro/steering/workflow.md`.
