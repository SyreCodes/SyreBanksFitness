# Azure deployment and handoff

Status: preparation in progress; **the application is not live**. No database, Redis instance, application, worker, migration job, or scheduled outbox job has been verified as deployed. GitHub automatic release remains disabled. This document records progress for resuming safely; it is not evidence that unexecuted steps succeeded.

## Confirmed resources

Subscription `686467b0-6295-4d5d-8fb6-d06fd003bde3`, tenant `53e15a06-0e85-4291-8864-7725106b0be2`, resource group `rg-syrebanks-prod`, region `southafricanorth`.

| Resource | Confirmed state |
| --- | --- |
| VNet `vnet-syrebanks-prod` | 10.42.0.0/16; app, PostgreSQL and private endpoint subnets created |
| Environment `cae-syrebanks-prod` | Created; private connectivity must still be tested from a running job |
| Log Analytics `law-syrebanks-prod` | Created, 30-day retention |
| Registry `acrsyrebanks686467b0` | Basic; public network enabled; authenticated image access; login server `acrsyrebanks686467b0.azurecr.io` |
| Identity `id-syrebanks-runtime` | Created; existing AcrPull, Blob Data Contributor, Key Vault Secrets User grants |
| Storage `stsyrebanks686467b0` | Public network disabled by policy; anonymous and shared-key access disabled; private container `syrebanks-media`; 14-day soft delete |
| Vault `kv-syrebanks-686467b0` | Public network disabled by governance, RBAC and purge protection enabled |
| Vault private endpoint `pe-syrebanks-keyvault` | Approved; DNS zone link `link-syrebanks-keyvault` completed and DNS zone group `default` succeeded |
| Blob private endpoint `pe-syrebanks-blob` | Approved and succeeded; Blob private DNS setup remains to be completed |
| PostgreSQL private DNS | `syrebanks.private.postgres.database.azure.com` linked to VNet |

Do not enable public Key Vault/storage access to work around governance. Cloud Shell outside the VNet cannot access private secrets or media. Use a temporary Container Apps job inside this environment to test private DNS, authenticate with a managed identity, and bootstrap secrets without printing them. Do not assume that the earlier `postgres-admin-password` write succeeded; distinguish SecretNotFound from a network/permission error before generating anything.

## Decisions still required

The preliminary managed-service estimate is roughly USD 200–240/month before tax, heavy video transfer, or unexpected logging, using a small PostgreSQL server and highly available Managed Redis. This is a planning estimate, not an Azure quote or hard cap. The user has not approved a monthly budget. Confirm sizing/costs before provisioning database/cache. The portal's subscription total includes other projects and is not a credit balance. ACR Premium is not needed for the currently confirmed public registry endpoint.

Select and verify a production email sender. The code requires STARTTLS SMTP with a valid certificate. A configured sender and real delivery test are prerequisites for registration/password reset; an empty SMTP configuration does not constitute a working production email service. Do not use the example Gmail address as an assumed authorized sender.

## Resume in Bash Cloud Shell

These initial commands inspect existing resources and complete Blob DNS. Run one command/block at a time and check the result. They contain resource identifiers only, no passwords.

```bash
az account set --subscription 686467b0-6295-4d5d-8fb6-d06fd003bde3
```

```bash
az network private-dns zone list -g rg-syrebanks-prod --query '[].name' -o table
```

If `privatelink.blob.core.windows.net` is absent, create it:

```bash
az network private-dns zone create -g rg-syrebanks-prod -n privatelink.blob.core.windows.net --query '{Zone:name}' -o json
```

```bash
az network private-dns link vnet list -g rg-syrebanks-prod -z privatelink.blob.core.windows.net --query '[].{Link:name,Network:virtualNetwork.id,State:virtualNetworkLinkState}' -o json
```

If no link to `vnet-syrebanks-prod` exists:

```bash
az network private-dns link vnet create -g rg-syrebanks-prod -z privatelink.blob.core.windows.net -n link-syrebanks-blob --virtual-network vnet-syrebanks-prod --registration-enabled false --query '{Link:name,State:virtualNetworkLinkState,Status:provisioningState}' -o json
```

```bash
az network private-endpoint dns-zone-group list -g rg-syrebanks-prod --endpoint-name pe-syrebanks-blob --query '[].{Name:name,Zones:privateDnsZoneConfigs[].privateDnsZoneId}' -o json
```

If there is no DNS zone group:

```bash
az network private-endpoint dns-zone-group create -g rg-syrebanks-prod --endpoint-name pe-syrebanks-blob -n default --private-dns-zone privatelink.blob.core.windows.net --zone-name blob --query '{Group:name,Status:provisioningState}' -o json
```

```bash
az network private-dns record-set a list -g rg-syrebanks-prod -z privatelink.blob.core.windows.net --query '[].{Name:name,Addresses:aRecords[].ipv4Address}' -o json
```

After DNS, the remaining bootstrap commands depend on the approved database/cache sizes and email sender. Do not substitute guesses. The order is: private connectivity test; isolated bootstrap identity; secret creation/reuse; private PostgreSQL and database; compatible non-clustered TLS Redis; least-privilege app DB account; runtime secrets; image build; migration; API/worker/outbox provisioning; admin creation; hosted acceptance; OIDC setup and enable automatic releases. A complete executable bootstrap sequence is still pending those choices.

## Runtime configuration

Serve the built React app and FastAPI from the same HTTPS origin using `Dockerfile.prod`, container port 10000. Set `ENVIRONMENT=production`, `PUBLIC_WEB_URL` and `ALLOWED_ORIGINS` to that origin, and use a unique JWT secret. Use `DATABASE_URL` with PostgreSQL certificate verification and an app-only database role. `REDIS_URL` must use `rediss://`, trusted CA and hostname verification; Celery requires a compatible non-clustered endpoint. Never disable certificate checks.

For media set `STORAGE_PROVIDER=azure`, `AZURE_STORAGE_ACCOUNT_URL=https://stsyrebanks686467b0.blob.core.windows.net`, `AZURE_STORAGE_CONTAINER=syrebanks-media`, and `AZURE_MANAGED_IDENTITY_CLIENT_ID=68624ec1-df89-4a74-a723-f557a426b9e4`. Attach the matching user-assigned identity to API/worker/jobs as needed. Azure media is proxied by the authorized API route, including GET ranges and HEAD; browser clients do not need direct Blob access or SAS credentials. Blob Delegator is unnecessary for this implementation.

Reference secrets in Key Vault using managed identity. Scope runtime secret permissions to app secrets before production; the runtime must not be able to retrieve the database administrator password. Use a separate temporary bootstrap identity for administrative initialization, then remove its grants. Do not put secret values into command output, Git, image layers, or workflow artifacts.

The worker command is `celery -A app.core.jobs.celery_app worker --loglevel=INFO --concurrency=1`. Keep one replica and use single revision mode. The manual migration job command must be exactly `alembic upgrade head`. The scheduled job command must be exactly `python -m app.dispatch_outbox`, normally once per minute. Each job uses parallelism 1 and replica completion count 1. Configure retry/timeout bounds. Email delivery is at-least-once; a process failure after SMTP acceptance can still produce a duplicate.

## Automatic releases

`ci.yml` runs web/API/browser/image quality checks. When `AZURE_DEPLOY_ENABLED=true` on the repository, it preserves the smoke-tested image as a one-day artifact, then calls `azure-release.yml`. Pull requests never deploy. The release job uses the `production` environment, OIDC, a concurrency lock, the tested image, and an immutable registry digest. A superseded main commit is refused.

Before enabling it, create the GitHub OIDC identity with issuer `https://token.actions.githubusercontent.com`, subject `repo:SyreCodes/SyreBanksFitness:environment:production`, and audience `api://AzureADTokenExchange`. Configure the GitHub production environment to permit main. Give the release identity only the needed registry push, app/job update/start/read, and managed identity assignment permissions scoped to this app's resources. OIDC access to modify jobs can use their attached identities, so do not attach the privileged bootstrap identity to release-managed jobs.

Set repository variables `AZURE_DEPLOY_ENABLED` (initially `false`), `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_ACR_NAME`, `AZURE_API_APP`, `AZURE_WORKER_APP`, `AZURE_MIGRATION_JOB`, and `AZURE_SCHEDULER_JOB`. Optional: `AZURE_IMAGE_REPOSITORY` (default `syrebanks-fitness`) and `AZURE_RUNNER_LABELS` (JSON array, default `["ubuntu-latest"]`). The confirmed public ACR supports the GitHub-hosted runner. If a future policy makes ACR private, use a suitably isolated runner with private connectivity; don't weaken the policy.

The script expects existing healthy single-container app/job resources. It runs migrations inside the VNet and waits for that exact execution, pins old API traffic while checking the candidate revision, updates and checks the worker/outbox, then switches API traffic. It checks `/ready` and the login page; this does not authenticate a real user. Failure restores old traffic/background images where possible. Migrations are never automatically downgraded. Keep migrations backward-compatible with the prior API/worker release.

## Completion checks

Before reporting production ready, test actual admin/client login and logout, password reset/registration email delivery, `/ready`, video upload/playback/seeking with authorization, a worker task, scheduled outbox dispatch, database backup restore, monitoring/alerts, and a main-branch CI deployment. Create the first administrator with `python -m app.bootstrap_admin` through an interactive terminal; never run development seed data in production. Existing local database data and uploaded media have not been migrated automatically.

## Source references

- [Container Apps jobs and permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [Container Apps releases from GitHub Actions](https://learn.microsoft.com/en-us/azure/container-apps/github-actions)
- [GitHub OIDC with Azure](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Key Vault private networking](https://learn.microsoft.com/en-us/azure/key-vault/general/private-link-service)
- [Azure Managed Redis capacity and availability](https://learn.microsoft.com/en-us/azure/redis/plan-tiers-and-capacity)
