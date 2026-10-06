#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-web}" in
  api)
    cd "$project_root/apps/api"
    exec env DATABASE_URL=sqlite:///./fitness-local.db REDIS_URL=redis://127.0.0.1:6379/0 MEDIA_ROOT="${MEDIA_ROOT:-$project_root/apps/api/private-media}" "$project_root/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000
    ;;
  seed)
    cd "$project_root/apps/api"
    env DATABASE_URL=sqlite:///./fitness-local.db REDIS_URL=redis://127.0.0.1:6379/0 "$project_root/.venv/bin/alembic" upgrade head
    exec env DATABASE_URL=sqlite:///./fitness-local.db REDIS_URL=redis://127.0.0.1:6379/0 "$project_root/.venv/bin/python" -m app.seed
    ;;
  web)
    cd "$project_root"
    exec npm run dev
    ;;
  *) printf 'Usage: bash scripts/dev.sh [web|api|seed]\n' >&2; exit 2 ;;
esac
