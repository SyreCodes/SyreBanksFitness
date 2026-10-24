# Azure production deployment

The application is hosted in **South Africa North** at:

**https://ca-syrebanks-api.orangemeadow-cb1b109d.southafricanorth.azurecontainerapps.io**

On 24 October 2026, hosted checks passed for `/ready`, the login page, administrator login/profile/session refresh/logout, exercise video upload/download/seeking/access control/removal, and Celery worker processing. Production was started fresh: no local database, demo seed, clients, programs or media were imported. The only user created during setup is the owner's first super administrator. Temporary exercise/media test records were removed after verification.

Email was explicitly deferred. Email verification and password-reset delivery are unavailable until SMTP is configured and tested. Registration itself can create an account without sending mail. Payment provider activation and other unfinished product features are separate from this hosting deployment.

## Resources and access

Subscription `686467b0-6295-4d5d-8fb6-d06fd003bde3`, tenant `53e15a06-0e85-4291-8864-7725106b0be2`, group `rg-syrebanks-prod`, region `southafricanorth`.

| Resource | Configuration |
| --- | --- |
| `cae-syrebanks-prod` | External Container Apps environment, Consumption profile, VNet integration |
| `ca-syrebanks-api` | Built React client and FastAPI on one HTTPS origin, port 10000, 0.5 CPU / 1 GiB, 1–2 replicas |
| `ca-syrebanks-worker` | Celery worker, 0.5 CPU / 1 GiB, one replica, single revision |
| `job-syrebanks-migrate` | Manual `alembic upgrade head`, one replica, separate migration identity |
| `job-syrebanks-outbox` | `python -m app.dispatch_outbox` every minute, one replica |
| `acrsyrebanks686467b0` | Basic registry, authenticated image access, admin account disabled |
| `pg-syrebanks-686467b0` | PostgreSQL 17, Standard_B1ms, 32 GiB, seven-day backups, private networking |
| `redis-syrebanks-prod` | Azure Managed Redis Balanced_B0, high availability, non-clustered, verified TLS, private endpoint |
| `stsyrebanks686467b0` | Private `syrebanks-media` container, managed identity access, shared keys/anonymous access disabled, 14-day soft delete |
| `kv-syrebanks-686467b0` | Private endpoint, RBAC, purge protection; per-secret application access |
| `law-syrebanks-prod` | Application/platform logs, 30-day retention |

The approved planning estimate is US$200–240/month before tax and heavy video traffic. It is not a spending cap.

`vnet-syrebanks-prod` uses 10.42.0.0/16. Subnets: Container Apps 10.42.0.0/23, PostgreSQL 10.42.2.0/24, private endpoints 10.42.3.0/24. Private DNS links cover PostgreSQL, Key Vault, Blob and Redis. Do not enable public data-service access to work around governance.

Runtime identity `id-syrebanks-runtime` reads only its application secrets, pulls images, and accesses the media container. `id-syrebanks-migrations` reads the migration connection secret and JWT secret and pulls images. The application database role cannot create tables or administer PostgreSQL; migrations use their own schema-owning role. Both database connections verify TLS certificates and hostnames. Browser media is served through the authorized API with GET/HEAD/range support; the browser never needs direct private Blob connectivity.

The three temporary setup jobs, bootstrap identity and its scoped grants were removed after initialization and hosted checks on 24 October. Their old initialization commands must not be treated as a routine deployment step. Do not run the development seed in production.

## Automatic releases

Completed, locally checked changes are committed and pushed to `origin main`. GitHub Actions runs frontend, API, browser and production-image quality gates. Local Codex edits alone do not deploy. A failed quality gate prevents release; a successful release is required before calling a new commit deployed.

The `production` environment accepts only `main`. The workflow uses GitHub OIDC with `id-syrebanks-github`; no long-lived Azure password is stored in GitHub. Its assignments are restricted to this application's registry, four app/job resources, runtime/migration identities, and Container Apps environment. Registry metadata requires Reader in addition to AcrPush.

Repository variables are configured for the subscription, tenant, release client identity, resource group, registry, API, worker, migration job and scheduler. **First-release blocker:** registry metadata Reader access is awaiting explicit approval. Automatic release is temporarily disabled (`AZURE_DEPLOY_ENABLED=false`) until this grant is approved. Set it to `true` only after that prerequisite is satisfied; hosted login and readiness have already passed. See the [latest GitHub Actions results](https://github.com/SyreCodes/SyreBanksFitness/actions) for the deployed commit and release outcome.

The release workflow downloads the exact production image that passed CI, pushes it to ACR and deploys its immutable digest. It runs a compatible migration inside the VNet, keeps traffic on the old API while checking the candidate, checks the updated worker and outbox execution, then promotes the API. Failure attempts to restore prior traffic and background images. Database migrations are never automatically downgraded. Keep every migration compatible with the previous API and worker release. Rollback logic has automated tests; a deliberate production failure drill has not been performed.

## Operational check and restart

Use a signed-in Azure Bash Cloud Shell, or a locally authenticated Azure CLI. The following commands print status only, without credentials.

```bash
az account set --subscription 686467b0-6295-4d5d-8fb6-d06fd003bde3
```

```bash
az postgres flexible-server show -g rg-syrebanks-prod -n pg-syrebanks-686467b0 --query '{State:state,PublicAccess:network.publicNetworkAccess}' -o json
```

Expected: `Ready`, `Disabled`.

**Known availability issue:** the activity log shows a service identity from another tenant stopped PostgreSQL at 22:08 UTC on 23 October 2026. Restarting it restored the app on 24 October. The caller was `da847d8c-ee71-44de-b462-6775e7d649a7`, application `a1a9c5b6-7a4f-4288-89ab-6805873f65d1`. The schedule and operator have not been identified. The subscription administrator must establish why it happened and whether this subscription can provide continuous production availability. Do not disable organization policies or automation without authorization.

If PostgreSQL is `Stopped`, resume the existing server:

```bash
az postgres flexible-server start -g rg-syrebanks-prod -n pg-syrebanks-686467b0
```

Wait until the status is `Ready`. Do not recreate the database or reset its passwords. Then check:

```bash
curl --fail --silent --show-error 'https://ca-syrebanks-api.orangemeadow-cb1b109d.southafricanorth.azurecontainerapps.io/ready'
```

Expected: `status: ready`, `database: connected`, `redis: connected`. Also verify actual login in the browser.

```bash
az containerapp revision list -g rg-syrebanks-prod -n ca-syrebanks-api --query '[].{Revision:name,Active:properties.active,Health:properties.healthState,Running:properties.runningState}' -o table
```

```bash
az containerapp job execution list -g rg-syrebanks-prod -n job-syrebanks-outbox --query '[].{Execution:name,Status:properties.status}' -o table
```

```bash
gh run list --repo SyreCodes/SyreBanksFitness --branch main --limit 5
```

Inspect the exact failing execution/release before retrying. If Azure reports registry not ready or a stopped database, diagnose that resource rather than broadening permissions. Never print connection URLs, tokens, secret values or Redis keys while troubleshooting.

## Account and data operations

The first administrator was created using the interactive `python -m app.bootstrap_admin` entry point. It refuses to run if a super administrator already exists. Its password was saved privately outside the repository and delivered to the owner; no password is included here. Do not rerun the bootstrap or seed to recover an existing account.

Before a substantial future schema change, check backup health and test recovery. Seven-day database backups and media soft delete are configured, but a restore drill has not been performed. Logs are available; dedicated availability alerts and a custom domain are not configured. Email delivery remains deferred. These limits should be resolved as the app moves from initial owner testing to wider client use.

## References

- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [GitHub OIDC with Azure](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Private Key Vault access](https://learn.microsoft.com/en-us/azure/key-vault/general/private-link-service)
- [Container Apps network rules](https://learn.microsoft.com/en-us/azure/container-apps/firewall-integration)
