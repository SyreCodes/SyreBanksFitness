# Development workflow

Read architecture/status before changing a domain. Keep business rules in services, use bounded repository helpers and validate public request schemas. Preserve separate program/price/legal snapshots and server-side ownership checks. Add a migration for every durable schema change.

Development commands and seeded accounts are in README.md. Run appropriate lint/type/tests after changes. Frontend API/unit/integration tests use Vitest/RTL; real-browser tests use Playwright against seeded local servers. Backend pytest uses isolated test databases. Tests that touch TestClient or bind local ports require sandbox escalation in this Codex environment.

The bundled Node24 executable here is `/home/syre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`; system Node18 is too old for Vite7. For this machine prepend that directory to PATH when running npm. This path is a local convenience, not a production requirement.

Use versioned environment configuration; never copy secrets into browser source or commits. `scripts/configure_local.py` generates a private `.env` with unique values. Browser storage holds only recoverable local drafts/preferences, never authentication tokens or authoritative coaching records.

Use synthetic seeded records to explore the coach/client surfaces. Authentic coach photos, biographical claims and consented transformation results must replace illustrative content before a brand launch. Legal content is a draft that requires jurisdiction-specific review.
