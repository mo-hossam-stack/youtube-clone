#!/usr/bin/env bash
# Host development runner: Docker infrastructure + Django runserver + Celery worker.
# Infrastructure is left running; use `make down` to stop it.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_FILE="${ENV_FILE:-backend/.env}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PWD/.venv}"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker is required for Postgres, Redis and ClamAV." >&2
  echo "Install Docker or add your user to the docker group, then retry." >&2
  exit 1
fi

COMPOSE=(docker compose --env-file "$ENV_FILE")

echo "==> Starting Postgres and Redis..."
"${COMPOSE[@]}" up -d --wait --wait-timeout 120 postgres redis

echo "==> Starting ClamAV..."
"${COMPOSE[@]}" up -d clamav
echo "==> Waiting for ClamAV (first run downloads signatures)..."
for _ in $(seq 1 180); do
  if "${COMPOSE[@]}" exec -T clamav clamdscan --ping 1 >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
if ! "${COMPOSE[@]}" exec -T clamav clamdscan --ping 1 >/dev/null 2>&1; then
  echo "ClamAV did not become ready. Check: ${COMPOSE[*]} logs clamav" >&2
  exit 1
fi

echo "==> Applying migrations..."
uv run --frozen python backend/manage.py migrate --noinput

WORKER_PID=""
cleanup() {
  if [ -n "$WORKER_PID" ]; then
    kill "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "==> Starting Celery worker..."
(cd backend && uv run --frozen celery -A config worker -l info --concurrency=2) &
WORKER_PID=$!

echo "==> Django: http://127.0.0.1:8000"
echo "    Ctrl+C stops Django and the worker; infrastructure keeps running (make down)."
uv run --frozen python backend/manage.py runserver "$@"
