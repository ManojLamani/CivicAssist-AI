# CivicAssist AI

Development foundation for an independent civic grievance platform for Bengaluru. Citizen authentication is available through the API; grievance features and government integrations are not implemented yet.

## Included

- Separate Next.js/TypeScript/Tailwind frontend and Python 3.12/FastAPI backend.
- Requested frontend/backend libraries, recorded in npm and uv lockfiles.
- PostgreSQL/PostGIS, Redis, Qdrant, and a Celery worker through Docker Compose.
- Environment examples, API health check, and basic CI checks.
- SQLAlchemy models and Alembic migrations for roles, users, departments, and department operators.
- Citizen registration, password login, and a protected current-user API.

## Run with Docker

Install Docker Desktop with Linux containers, then run from the repository root:

```powershell
Copy-Item .env.example .env
docker run --rm python:3.12-slim-bookworm python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" | Add-Content .env
docker compose up --build -d --wait --wait-timeout 300
```

Frontend: <http://localhost:3000>. API docs: <http://localhost:8000/docs>. Process health: <http://localhost:8000/api/v1/health>.

Compose runs database migrations before starting the API. Only the three role names are seeded; no accounts, departments, or government responsibility mappings are seeded. The API requires a unique `JWT_SECRET` of at least 32 characters and rejects startup without it.

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

For native development, copy the root `.env.example` to `.env` and generate `JWT_SECRET` before starting the API. From the root, use `uv run --project backend python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" | Add-Content .env`. Configuration reads that file; shell variables take precedence. Commit successful writes explicitly when using the session dependency; unfinished transactions roll back when the session closes.

To create a schema migration: `uv run alembic revision --autogenerate -m "describe change"`. Review generated SQL before applying it. To roll back this initial schema on a disposable database: `uv run alembic downgrade base` (deletes the identity/department tables, retains PostGIS).

Autogeneration only inspects mapped application tables, leaving extension-owned and unrelated tables alone. Removing a table requires an explicit reviewed `op.drop_table` migration.

PostgreSQL integration tests run automatically in CI. To run locally from `backend/`:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://civicassist:civicassist_local@localhost:5432/civicassist"
uv run pytest
```

Tests create a random schema inside a transaction and roll it back. Without `TEST_DATABASE_URL`, database and authentication integration tests are skipped. Tests cover migrations, constraints, registration, password hashing, login, and rejected credentials/tokens. Never commit real credentials.

## Authentication API

- `POST /api/v1/auth/register`: JSON `email`, `password`, `full_name`. Passwords must contain 12–128 characters. Emails are trimmed and lowercased. Registration always creates a citizen; role fields and other extra fields are rejected. Returns public user fields, or HTTP 409 for an existing email.
- `POST /api/v1/auth/login`: JSON `email`, `password`. Returns `access_token`, `refresh_token`, `token_type: bearer`, and `expires_in: 900`. Invalid credentials return the same HTTP 401 response for unknown users and incorrect passwords.
- `POST /api/v1/auth/refresh`: JSON `refresh_token`. Returns a new token pair and consumes the supplied refresh token. Sessions have an absolute seven-day lifetime from login. Only SHA-256 hashes of randomly generated refresh tokens are stored in the database. Reusing a consumed token revokes that entire login session, including its current access token; clients must serialize refresh requests and replace the saved refresh token after every successful rotation.
- `POST /api/v1/auth/logout`: JSON `refresh_token` from that login (current or previously rotated). Revokes that session immediately and returns HTTP 204, including for unknown/already logged-out tokens. Other login sessions stay active. An unexpired access token is not required for refresh or logout.
- `GET /api/v1/auth/me`: send `Authorization: Bearer <access_token>`. Returns the current database user and role; invalid/expired tokens and deleted users return HTTP 401.

Use the API docs to register and log in, then paste the token into **Authorize** to try `/auth/me`. Passwords are stored using Argon2id. JWT validation fixes the signing algorithm, issuer, audience, expiry, and token type. Token responses disable caching and never return password hashes.

Access tokens expire after 15 minutes and are checked against their database session on protected requests, so logout and refresh-token replay revoke access immediately. Tokens issued before this session migration lack the required session ID; log in again after upgrading. Apply `uv run alembic upgrade head` for native development; Compose runs the migration automatically. Downgrading this migration deletes login sessions and refresh-token history.

Email verification, password reset, login throttling, role-protected administrative endpoints, and frontend auth screens/storage remain separate follow-ups. Refresh tokens are credentials: keep them private and out of URLs/logs. Local HTTP is for development; deployed authentication requires HTTPS.
