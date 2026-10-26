# Capacity target and validation

The requested target is at least 1,000 registered accounts and 1,000 simultaneously active users. That is a target, not a verified production rating. On 26 October 2026 the owner chose to retain the current budget and defer paid upgrades; production sizing therefore remains unchanged. No finite deployment can promise to handle arbitrary traffic without errors.

## Current constraints

Production currently uses a PostgreSQL B1ms server with a configured maximum of 50 connections. Microsoft documents 35 available user connections for this size; reserved connections must not be counted as app capacity. The saved deployment configuration permits one to two API replicas at 0.5 CPU / 1 GiB each, and one worker. These settings have not been certified for 1,000 active users. Repeated subscription suspension is an independent availability blocker even if application capacity is sufficient.

Each API/worker process has its own SQLAlchemy pool. Database-backed requests wait asynchronously for a session slot before entering the shared thread pool. This prevents waiting authentication dependencies from occupying the threads needed by requests that already hold connections. Waiting is bounded, and cancellation always returns the slot and rolls back uncommitted work. New defaults bound each pool to three connections with no overflow and a five-second wait, and recycle connections after five minutes. Database dependencies close before response bodies are sent, so slow video downloads do not reserve a database connection for their duration. A full pool responds with HTTP 503 and `Retry-After`, rather than opening unlimited connections or exposing an internal error. This protects database capacity; it does not make overload a successful request. Set `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT`, `DATABASE_POOL_RECYCLE`, and `DATABASE_CONNECT_TIMEOUT` explicitly when sizing a deployment.

Budget peak connections across **both old and new revisions during releases**, every worker process, scheduled and migration jobs, and an administrative reserve. With four API replicas during overlap, two worker processes during a worker replacement, and two one-process jobs, the conservative default ceiling is 8 × 3 = 24 connections, below the B1ms user limit. Raising replica/process counts requires recalculating this budget. Do not simply increase PostgreSQL `max_connections` on a small server to mask insufficient capacity.

## Repeatable local baseline

Use a separate localhost PostgreSQL database whose name ends in `_loadtest`. The fixture generator refuses production mode, remote database hosts and databases containing users. It creates synthetic client accounts, three habits and five notifications per account. It never imports production data or sends email. Its short-lived access tokens are saved in a new private file outside Git.

With API development dependencies installed, run from the repository root (substitute your local database port and user):

```bash
export ENVIRONMENT=loadtest
export DATABASE_URL=postgresql+psycopg://127.0.0.1:55438/sbf_loadtest
export JWT_SECRET=local-capacity-test-only-not-a-production-secret
export STORAGE_PROVIDER=local
export DATABASE_POOL_SIZE=3
export DATABASE_MAX_OVERFLOW=0
export PYTHONPATH="$PWD/apps/api"
```

Create the schema in this disposable database:

```bash
(cd apps/api && python -m alembic upgrade head)
```

Create the 1,500 synthetic clients and a private token file (the destination must not exist):

```bash
python scripts/load/seed_clients.py --users 1500 --output /tmp/sbf-load-clients.json
```

In a separate terminal with the same environment, start a dedicated local API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 18091 --no-access-log
```

For a multi-process comparison, stop that server and start it with `--workers 4`. Each process has its own pool, so this permits twelve connections with the defaults. Keep the same database, fixture and test duration for comparison.

Run the load generator in the first terminal:

```bash
python scripts/load/run_clients.py --clients /tmp/sbf-load-clients.json --users 1500 --ramp 30 --hold 120 --pace 5 --output /tmp/sbf-load-result.json
```

This ramps to 1,500 distinct pre-authenticated clients. Each attempts one action every five seconds: 80% profile/habit/notification/program reads and 20% habit-log writes. The full population targets roughly 300 requests/second if response times allow. It measures response time and all non-200 responses, including overload responses. Exit success requires under 1% errors, plateau p95 below two seconds, and every target user observed. The script only accepts localhost HTTP origins, follows no redirects, and prints no tokens.

A pass establishes only this synthetic profile on that local hardware. It excludes simultaneous password hashing, video playback/upload bandwidth, payments, real-world data volume, distributed infrastructure and Azure scale-out latency. Tokens expire normally; regenerate the isolated fixture database for later runs. Stop the local API/database and remove the temporary token file when finished.

## Measured local results — 26 October 2026

Same 1,500 distinct clients, 30-second ramp, 120-second plateau, five-second action pacing, local PostgreSQL 16, and three database connections per API process. The development machine has 16 logical CPUs and roughly 13 GiB RAM; processes were not restricted to Azure container CPU/memory limits. The test driver uses aiohttp and counts timeouts and busy responses as errors.

| Configuration | Requests | Successful HTTP 200 | Errors | Plateau p95 | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| One process, bounded pool, before asynchronous admission | 20,599 | 2,573 | 87.51% | 11.00 s | Fail |
| One process, asynchronous admission | 41,110 | 32,089 | 21.94% | 5.11 s | Fail |
| Four processes, asynchronous admission, 12 total connections | 41,244 | 41,244 | 0% | 0.0144 s | Pass |

The first run had 17,949 client timeouts and 77 busy responses. The corrected one-process run had no client timeouts, but 9,021 busy responses: it still failed the capacity target. The four-process plateau completed 35,994 requests in 120 seconds, about 300 requests/second. This demonstrates the benefit of the fix and distributing this workload, not equivalent performance on current Azure hosting. The short test and sparse synthetic data do not establish sustained production capacity or video/login throughput.

Regression validation: 149 API tests passed (one integration test skipped), type checks passed, lint passed, and all 24 Azure release tests passed. Concurrency coverage exercises authentication holding a connection before endpoint scheduling, timeout/cancellation recovery, rollback and early release before streaming.

## Required cloud validation

Before describing production as ready for this target:

1. Keep the subscription continuously enabled and resolve the external overnight shutdown/suspension policy through its owner.
2. Use a separately approved staging environment with the same network, database tier, storage behavior and scaling settings as production. Do not stress production or seed it with test accounts.
3. Run sustained authenticated mixed read/write traffic, login/refresh bursts, representative data volume, authorized video playback/range requests and upload contention. Include a 1,000-user plateau, a higher burst and recovery after load falls. Record request rate, latency, errors, database connections/CPU/IO, replica scale events, queue delay and memory.
4. Confirm tenant/owner isolation and session revocation under load, and validate rolling deployment while traffic continues. All 503/429 responses count toward the workload error budget; do not hide them.
5. Approve a measured capacity/cost plan before changing paid infrastructure. A General Purpose PostgreSQL tier enables built-in PgBouncer; its use requires compatibility tests and updating the runtime connection endpoint. Migrations should retain a direct database connection.

Video delivery currently passes through the authenticated API because Blob storage is private. A thousand simultaneous video viewers can dominate bandwidth and cost independently of API requests. A different delivery architecture requires preserving access checks; publicizing the blob container is not an acceptable scaling fix.

## Price reference, checked 26 October 2026

Azure public retail rates for South Africa North in USD show PostgreSQL Flexible Server General Purpose Ddsv5, two cores, at **$0.235/hour**, about **$171.55/month** at 730 hours. Two continuously active API replicas, each one CPU and two GiB, cost about **$157.68/month** at the listed active CPU/memory rates. Their combined **$329.23/month compute subtotal** already exceeds the earlier $200–240 overall setup estimate. It excludes database storage/backup/HA, existing Redis, worker/jobs, logging, networking, requests, transfer, taxes and staging. Discounts and free grants are excluded; extra replicas and video traffic increase the total. These are sizing examples, not evidence that those sizes meet the target and not authorization to purchase them.

Sources: [Azure retail price API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices), [PostgreSQL connection limits](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/concepts-limits), [PgBouncer](https://learn.microsoft.com/en-us/azure/postgresql/connectivity/concepts-pgbouncer), [Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app).

Implementation references: [FastAPI dependency cleanup scopes](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/). Database cleanup uses a separate bounded thread limiter so connection release cannot wait behind the request work it is meant to unblock.
