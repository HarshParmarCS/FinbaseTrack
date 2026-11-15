# FinTasks Backend

FastAPI + SQLAlchemy 2.0 + PostgreSQL. Current state: **milestones M1 to M7** (foundation, schema, authentication, PBAC engine, projects and members, tasks, dashboard and activity). Exposed: health, `/api/v1/auth/*`, `/api/v1/projects` and `/api/v1/projects/{id}/members`. `/api/v1/projects/{id}/tasks`, `/api/v1/tasks/{id}` and `/api/v1/tasks/{id}/status`. Every service calls the PBAC engine before mutating. Also exposed: `/api/v1/dashboard/stats`, `/api/v1/dashboard/activity` and `/api/v1/projects/{id}/activity`. Not built yet: frontend.

All commands below run from the `backend/` folder.

## 1. Prerequisites

- Python **3.12** (the project targets 3.12; macOS often ships 3.13, so use `uv` or install 3.12).
- Podman (or Docker) with `podman compose` / `docker compose`. Alternatively any PostgreSQL 14+ server you can log into.

## 2. Create the virtual environment and install dependencies

Option A, with [uv](https://docs.astral.sh/uv/) (downloads Python 3.12 if missing):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

Option B, with plain Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements.txt` holds runtime dependencies (used by the Docker image later). `requirements-dev.txt` adds pytest, ruff, mypy and the test HTTP client.

## 3. Start PostgreSQL (Podman or Docker) and configure `.env`

PostgreSQL 16 runs in a container defined by `docker-compose.yml` at the repository root. The same file works with Podman and Docker.

```bash
cd ..                                   # repository root
cp .env.example .env                    # compose credentials: set POSTGRES_PASSWORD (openssl rand -hex 16)
podman compose up -d db                 # or: docker compose up -d db
podman ps                               # fintasks-db should become (healthy)
```

This creates two databases, `fintasks` (development) and `fintasks_test` (tests), published on `127.0.0.1:5433` (5433 avoids a clash with a PostgreSQL already using 5432). The test database is created by `infra/postgres/init/01-create-test-database.sh`, which runs only the first time the data volume is created.

Then configure the backend (`.env` is git-ignored). Use the same password as the root `.env`:

```bash
cd backend
cp .env.example .env
```

```
DATABASE_URL=postgresql+psycopg://fintasks:<password>@localhost:5433/fintasks
TEST_DATABASE_URL=postgresql+psycopg://fintasks:<password>@localhost:5433/fintasks_test
```

Notes:
- The URL must be PostgreSQL. SQLite and other databases are rejected at startup.
- A password with special characters (`@`, `/`, `:`) must be URL-encoded. `openssl rand -hex 16` avoids the issue.
- The test database name must end with `_test`. The tests refuse to run otherwise.
- Real environment variables take precedence over `.env`.
- Stop the database with `podman compose down` (data is kept). `podman compose down -v` also deletes the data, and the init script runs again on the next start.
- If you use Podman, the Podman machine must be running (`podman machine start`).

## 4. Apply migrations

```bash
alembic upgrade head                 # create/update all tables (one migration so far: initial schema)
alembic current                      # show the applied revision
alembic downgrade base               # remove every table (development only)
alembic check                        # fails if the models differ from the migrations
alembic upgrade head --sql           # print the SQL instead of running it
```

Create a migration after changing a model:

```bash
alembic revision --autogenerate -m "describe change"
```

Always read the generated file before applying it: autogenerate cannot express everything (extensions, deferred or circular constraints, some index options). The schema is documented in `../docs/database-design.md`; update that document first.

## 5. Run the API

```bash
uvicorn app.main:app --reload
```

- Health check: `http://localhost:8000/api/v1/health` returns `{"data": {"status": "ok"}}`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

Every response carries an `X-Request-ID` header (a safe client-supplied one is echoed). Logs are readable text in `development` and one-line JSON in `test` and `production`.

## 6. Authentication quick start

Set `JWT_SECRET_KEY` in `.env` first (at least 32 characters; see `.env.example`). Tokens travel only in cookies; use `-c`/`-b` with curl to keep them:

```bash
# register (logs you in), then read your profile
curl -i -c jar.txt -H 'Content-Type: application/json' \
  -d '{"name":"Ana Lopez","email":"ana@example.com","password":"correct-horse-battery"}' \
  http://localhost:8000/api/v1/auth/register
curl -b jar.txt http://localhost:8000/api/v1/auth/me

# state-changing calls with a session also need the CSRF header (value of the csrf_token cookie)
CSRF=$(awk '$6=="csrf_token"{print $7}' jar.txt)
curl -i -b jar.txt -c jar.txt -X POST -H "X-CSRF-Token: $CSRF" http://localhost:8000/api/v1/auth/refresh
curl -i -b jar.txt -c jar.txt -X POST -H "X-CSRF-Token: $CSRF" http://localhost:8000/api/v1/auth/logout
```

Swagger UI can register, log in and call `/auth/me` (cookies are stored by the browser). `refresh` and `logout` need the `X-CSRF-Token` header, which Swagger UI cannot add automatically; use curl for those. The full contract is `../docs/api-contract.md`.

> **Never `pip install jwt`.** PyJWT (installed from `requirements.txt`) provides the `jwt` module; the unrelated PyPI package named `jwt` overwrites it and breaks token handling (`module 'jwt' has no attribute 'encode'`). If it happens: `pip uninstall jwt pyjwt && pip install -r requirements-dev.txt`.

## 7. Tests and quality checks

```bash
pytest                    # needs TEST_DATABASE_URL (see step 3); migrates the test database itself
ruff check . && ruff format --check .
mypy
pytest --cov=app          # coverage (99% at M7)
python -m scripts.generate_api_docs   # regenerates docs/api-contract.md section 3, docs/openapi.json, app/api/examples.json
```

`tests/audit/test_guards.py` fails if the contract or `docs/openapi.json` is out of date, so run the generator after changing a route or schema.

## Layout

```
app/
  main.py            application factory (create_app) and module-level app
  core/              config, logging, exceptions, middleware, cookies, csrf, clock
  database/          Base (naming convention), engine and request-scoped session
  api/               router.py mounts /api; v1/router.py mounts /v1 and the routers
  routers/           HTTP only: parse input, call a service, return the envelope
  schemas/           Pydantic request/response models and shared envelopes
  services/          business logic and transactions (auth_service.py)
  repositories/      database queries only (users, refresh tokens)
  models/            ORM models: user, project, project_member, task, activity_log, refresh_token
  authorization/     PBAC: engine (PDP), service (PEP), information (PIP), policies.json (PAP)
  auth/              passwords.py (Argon2id), tokens.py (JWT), dependencies.py (get_current_user)
alembic/             migrations (URL comes from DATABASE_URL, never alembic.ini)
tests/               pytest suite against a real PostgreSQL database (tests/models/ covers the schema)
```
