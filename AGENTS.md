# Syre Banks Fitness repository workflow

The `main` branch of `https://github.com/SyreCodes/SyreBanksFitness.git` is the source of truth. GitHub Actions checks pushes and pull requests to `main`. Azure hosts the app in South Africa North. Hosted login, media and worker checks passed on 24 October 2026. The first GitHub release is pending approval for registry metadata Reader access; AZURE_DEPLOY_ENABLED is temporarily false until that prerequisite is satisfied. Local edits alone never update a hosted app. Follow docs/AZURE_DEPLOYMENT.md for deployment prerequisites and verified status; distinguish the live site from the still-unverified automatic release. Do not import local/demo data or run the production seed; email delivery is deliberately deferred.

For completed changes intended for GitHub, run the relevant local quality checks, commit the task's source changes, and push to `origin main` so CI can check them. Do not push failing or incomplete changes. Follow any newer user request for a review, branch, PR, or local-only work instead. Never commit `.env`, credentials, local databases, or uploaded media.

When changing the database, keep migrations compatible with the previous API and worker release because future services may roll out separately. Once hosting is configured, validate login, `/ready`, and the changed user flow after deployment.
