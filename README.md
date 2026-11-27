# CivicAssist AI

Basic development setup for an independent civic grievance platform for Bengaluru. No product features or government integrations are implemented yet.

## Included

- Separate Next.js/TypeScript/Tailwind frontend and Python 3.12/FastAPI backend.
- Requested frontend/backend libraries, recorded in npm and uv lockfiles.
- PostgreSQL/PostGIS, Redis, Qdrant, and a Celery worker through Docker Compose.
- Environment examples, API health check, and basic CI checks.
- SQLAlchemy models and Alembic migrations for roles, users, departments, and department operators.

## Run with Docker

Install Docker Desktop with Linux containers, then run from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d --wait --wait-timeout 300
```

Frontend: <http://localhost:3000>. API docs: <http://localhost:8000/docs>. Process health: <http://localhost:8000/api/v1/health>.

Compose runs database migrations before starting the API. The database contains the three role names only; no accounts, departments, or government responsibility mappings are seeded. This schema does not yet implement authentication or role-based authorization.

```powershell
docker compose exec -T backend python -c "from app.workers.celery_app import ping; assert ping.delay().get(timeout=30) == 'pong'"
docker compose down
```

`down` preserves database volumes. Ports bind to localhost. The example credentials and Compose configuration are for local development only. `NEXT_PUBLIC_API_URL` is embedded at frontend build time; rebuild when changing it.

If port 8000 is occupied, set `BACKEND_PORT=8010` and `NEXT_PUBLIC_API_URL=http://localhost:8010` in `.env` before building.
If port 3000 is occupied, set `FRONTEND_PORT=3010` and `FRONTEND_URL=http://localhost:3010`.

## Native development

Prerequisites: Node.js 24 LTS, npm, and [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installs the required Python 3.12 without replacing global Python.

```powershell
docker compose up -d postgres redis qdrant
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

In a second terminal from the repository root:

```powershell
cd backend
uv sync --locked --extra ml
uv run --extra ml alembic upgrade head
uv run --extra ml uvicorn app.main:app --reload
```

The `ml` extra installs Sentence Transformers and faster-whisper. Model weights are not downloaded during setup. Use `uv sync --locked` for a lightweight API environment. OCR's Tesseract executable with English, Hindi, and Kannada data is included in Docker; native OCR development needs a separate Tesseract installation. No API key is required to run this setup.

For a native Windows worker, run `uv run celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=info`. Docker uses Linux workers. Native worker environment variables must be exported in the shell; Compose provides them automatically.

## Checks

```powershell
cd frontend
npm run typecheck
npm run build
cd ../backend
uv run ruff check .
uv run pytest
cd ..
docker compose config --quiet
```

For native database commands, copy the root `.env.example` to `.env` first. Configuration reads that file; shell variables take precedence. Commit successful writes explicitly when using the session dependency; unfinished transactions roll back when the session closes.

To create a schema migration: `uv run alembic revision --autogenerate -m "describe change"`. Review generated SQL before applying it. To roll back this initial schema on a disposable database: `uv run alembic downgrade base` (deletes the identity/department tables, retains PostGIS).

Autogeneration only inspects mapped application tables, leaving extension-owned and unrelated tables alone. Removing a table requires an explicit reviewed `op.drop_table` migration.

PostgreSQL integration tests run automatically in CI. To run locally from `backend/`:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://civicassist:civicassist_local@localhost:5432/civicassist"
uv run pytest
```

Tests create a random schema inside a transaction and roll it back. Without `TEST_DATABASE_URL`, database tests are skipped. They verify migrations, model/schema agreement, persistence, rollback, unique constraints, and foreign keys. No authentication endpoints, complaint tables, maps, RAG pipelines, or administrative APIs are implemented yet. Never commit real credentials.
