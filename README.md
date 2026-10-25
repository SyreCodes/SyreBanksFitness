# Syre Banks Fitness

A modular fitness coaching platform with a React 19 client and FastAPI API. Public marketing, applications/CRM, client assessment, program snapshots, workout logging, progress, habits, check-ins, private messaging, booking, editable products/content, media and audit records are connected to durable API models.

See [implementation status](docs/IMPLEMENTATION_STATUS.md) for verified scope and outstanding work. The app is hosted on Azure for owner testing. See [Azure deployment](docs/AZURE_DEPLOYMENT.md) for verified checks, access, and remaining release prerequisites.

## GitHub publication and quality checks

The app is hosted in Azure South Africa North: [open Syre Banks Fitness](https://ubuntustar.com). GitHub Actions checks the frontend, API, browser flows, and production image on every push and pull request to `main`. Automatic Azure releases are enabled and require every quality gate to pass. Custom-domain administrator login and runtime recovery passed on 25 October 2026. The operational guide records a recurring external database shutdown that still needs subscription-administrator investigation. Check the Actions release result before treating a commit as deployed. See the [deployment guide](docs/DEPLOYMENT.md) and [Azure operational guide](docs/AZURE_DEPLOYMENT.md). Local edits alone do not deploy.

## Requirements

- Node.js 22.12 or newer (24 is available in this Codex workspace), npm, Python 3.12.
- Docker with Compose and permission to access the Docker daemon for PostgreSQL/Redis/MinIO.
- Merchant and mail credentials only when testing real payments and mail.

## Docker development

```sh
python3 scripts/configure_local.py
docker compose up --build
docker compose exec api python -m app.seed
```

The configuration script generates unique development secrets and refuses to overwrite an existing `.env`. Alternatively copy `.env.example` to `.env` and replace every marked placeholder. Seed passwords must be supplied; they are never embedded in application source. Seeding is development-only and idempotent, and does not fabricate completed payments, invoices, subscriptions or client consent.

- Frontend: http://localhost:5173
- Admin workspace: http://localhost:5173/admin
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- MinIO console: http://localhost:9001

The API applies Alembic migrations on startup. Redis and the Celery worker run in Compose. MinIO is available for adapter development; `STORAGE_PROVIDER=local` stores validated private assets in the API volume until an S3 bucket/access configuration is provided.

## Local fallback without Docker

SQLite is an explicit development/test fallback. It does not verify PostgreSQL semantics or Redis coordination.

```sh
python3 -m venv .venv
.venv/bin/pip install -e 'apps/api[dev]'
npm ci
python3 scripts/configure_local.py
cd apps/api
DATABASE_URL=sqlite:///./fitness-local.db ../../.venv/bin/alembic upgrade head
DATABASE_URL=sqlite:///./fitness-local.db ../../.venv/bin/python -m app.seed
cd ../..
bash scripts/dev.sh api
```

`scripts/dev.sh api` points local media storage at `apps/api/private-media` even if an older `.env` still has the Docker-only `/app/private-media` path. Container startup continues to mount `/app/private-media`. Exercise demonstrations accept MP4, WebM, or MOV files up to `VIDEO_MAX_UPLOAD_MB` (100 MB by default); the browser reads this limit from the API. Other media retains its separate 10 MB limit.

In another terminal at the repository root run `npm run dev`. Vite proxies API/media requests to port 8000. Its environment directory is the repository root; only `VITE_` keys become browser-visible. Access tokens remain in memory; refresh credentials use HttpOnly cookies.

## Development accounts

- Super admin: `admin@syrebanksfitness.local`, password from `SEED_ADMIN_PASSWORD` in the generated `.env`.
- Coach: `coach@syrebanksfitness.local`, password from `SEED_ADMIN_PASSWORD`.
- Client: `client@syrebanksfitness.local`, password from `SEED_CLIENT_PASSWORD`.

Use these only on local development. Sign in as the super admin to open the command center and Users & access page. The public registration path uses normal email validation and cannot create staff roles.

## Quality gates

```sh
npm run lint
npm run typecheck
npm test
npm run build
.venv/bin/ruff check apps/api
cd apps/api
../../.venv/bin/mypy app
DATABASE_URL=sqlite:///./fitness-local.db ../../.venv/bin/pytest -q
```

Real-browser tests require seeded running API/web servers and seed credentials from the environment or local `.env`:

```sh
# Install the Playwright Chromium runtime once, or provide an installed Chrome binary.
npx playwright install chromium
PLAYWRIGHT_CHROME=/usr/bin/google-chrome npm run test:e2e --workspace @syre/web
```

The E2E suite creates clearly named synthetic acceptance records in the development database. API tests use isolated temporary databases. CI runs frontend gates, backend lint/type/tests and PostgreSQL migrations, browser acceptance against a disposable database, and the production Docker build. CI itself must be observed in GitHub before claiming a CI pass.

## Configuration & deployment

Never commit `.env`. Production requires PostgreSQL, a unique JWT secret, HTTPS origins, production cookie settings, live Redis, private object storage, database backups and tested migrations. Configure email, Flutterwave and optional OAuth providers on the server. Checkout redirects never activate a plan; the backend verifies provider transactions and deduplicates financial writes.

See [architecture](docs/ARCHITECTURE.md), [database](docs/DATABASE.md), [API](docs/API.md), [security](docs/SECURITY.md), [integrations](docs/INTEGRATIONS.md), [deployment](docs/DEPLOYMENT.md), and [development](docs/DEVELOPMENT.md).
