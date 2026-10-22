# Syre Banks Fitness repository workflow

The `main` branch of `https://github.com/SyreCodes/SyreBanksFitness.git` is the source of truth. GitHub Actions checks pushes and pull requests to `main`. Azure production setup is in progress in South Africa North. The Azure release workflow is disabled until the resources and GitHub OIDC settings are verified and AZURE_DEPLOY_ENABLED is set to true. Local edits alone never update a hosted app. Follow docs/AZURE_DEPLOYMENT.md for deployment prerequisites and verified status; do not describe the site as live until hosted checks pass.

For completed changes intended for GitHub, run the relevant local quality checks, commit the task's source changes, and push to `origin main` so CI can check them. Do not push failing or incomplete changes. Follow any newer user request for a review, branch, PR, or local-only work instead. Never commit `.env`, credentials, local databases, or uploaded media.

When changing the database, keep migrations compatible with the previous API and worker release because future services may roll out separately. Once hosting is configured, validate login, `/ready`, and the changed user flow after deployment.
