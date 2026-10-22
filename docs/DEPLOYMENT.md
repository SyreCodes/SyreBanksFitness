# GitHub and deployment workflow

The current release target is the [SyreCodes/SyreBanksFitness repository](https://github.com/SyreCodes/SyreBanksFitness), on its `main` branch. GitHub stores the source and runs [quality gates](../.github/workflows/ci.yml); it does **not** run this React/FastAPI application as a hosted service. Azure production setup is in progress. The optional Azure release job stays disabled until its prerequisites are configured; see [Azure deployment](AZURE_DEPLOYMENT.md). Local Codex edits reach GitHub only after they are committed and pushed.

## Repository workflow

1. Run the relevant local checks in the [README](../README.md#quality-gates), then commit complete source changes. Keep `.env`, credentials, local databases, and uploaded media out of Git.
2. Push the commit to `origin main`. GitHub Actions runs frontend lint, typecheck, tests and build; API lint, typecheck, tests and PostgreSQL migrations; browser acceptance against disposable services; and a production Docker image build and smoke test.
3. Check the [Actions tab](https://github.com/SyreCodes/SyreBanksFitness/actions) for that commit. A successful local run does not establish that CI passed. Fix any failing job and push another tested commit.

The [production Dockerfile](../Dockerfile.prod) remains a portable build artifact and CI smoke target. It builds the React app with `VITE_API_URL=/api/v1` and `VITE_DEMO_MODE=false`, then serves it with FastAPI on one origin. It does not deploy a container by itself. `docker-compose.yml` remains the local development setup.

## Other hosting options

Vercel is a possible **later** host, but no Vercel project, deployment workflow, or billing has been set up. The app needs a live PostgreSQL database, Redis, a Celery worker and scheduler, private object storage for uploads, migrations, TLS, secrets, backups, and production checks. The browser's session and CSRF cookies also need `/api/v1` to work through the same HTTPS origin as the frontend, or a tested auth redesign. A frontend-only Vercel import would leave the app's data and login flows unavailable.

[Vercel supports FastAPI as a Function](https://vercel.com/docs/frameworks/backend/fastapi), but its [Function request and response body limit is 4.5 MB](https://vercel.com/docs/functions/limitations#request-body-size). This app currently streams exercise videos up to 100 MB through its API, so that upload flow would need direct-to-object-storage uploads or a separately hosted API. The current Celery worker and 60-second Beat schedule need a service that runs those processes; [Vercel Cron invokes Functions](https://vercel.com/docs/cron-jobs), and the [Hobby plan permits at most daily cron runs](https://vercel.com/docs/cron-jobs/usage-and-pricing). These are design and acceptance tasks for the future Vercel deployment, not prerequisites for publishing the code to GitHub now.

For the authorized Azure rollout, configure secrets outside Git, run compatible migrations, and verify hosted login, `/ready`, video upload/playback, worker jobs, and backup restore. Keep schema migrations compatible with the previous API and worker release during any separate service rollouts.
