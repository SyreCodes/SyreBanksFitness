# Database and migration map

SQLAlchemy 2 models use UUID string primary keys and UTC creation/update timestamps. Alembic owns schema creation; application startup never substitutes `create_all` for production migrations.

Implemented model groups live under `apps/api/app/modules`: auth (users, refresh sessions and action tokens); clients (assessment, screening, versioned consent and private coach notes); leads (pipeline/application responses/follow-up); coaching (exercise catalog, reusable program JSON, immutable assignment snapshots, sessions and weight measurements); experience (habits/logs, weekly check-ins, private messages and notifications); scheduling (bookings); commerce (products, snapshotted orders, verified payments, subscriptions and invoices); CMS (editable business content, blog and media); admin (audit).

These are the implemented MVP entities, not the full future entity list in the master brief. Workouts and sets currently live as validated JSON snapshots rather than separate per-week/exercise-log tables. Broader custom measurements, recipe/meal libraries, configurable check-in question tables, role-permission join tables and referral/community entities remain future schema work.

```sh
cd apps/api
../../.venv/bin/alembic upgrade head
../../.venv/bin/alembic current
../../.venv/bin/alembic revision --autogenerate -m 'describe the schema change'
```

Review generated migrations before applying them. Use `docker compose exec api alembic upgrade head` for Compose. Preserve order/product/assignment/consent snapshots; editing source templates must not change historical records. Cancellation preserves booking history. Media deletion archives the asset and removes public access.

SQLite verification does not establish PostgreSQL constraint/concurrency correctness. A production migration should run against a recent backup restored in staging, with a tested rollback/restore plan.
