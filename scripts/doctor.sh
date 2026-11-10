#!/usr/bin/env bash
# Context-aware project diagnostics.
# Usage: ENV_FILE=backend/.env ./scripts/doctor.sh [dev|test|prod]
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

MODE="${1:-dev}"
ENV_FILE="${ENV_FILE:-backend/.env}"
FAILURES=0
WARNINGS=0

ok() { printf '  OK    %s\n' "$1"; }
warn() { printf '  WARN  %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

get_value() {
  sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null \
    | head -n1 \
    | sed -E 's/[[:space:]]+#.*$//' \
    | tr -d '"' \
    | tr -d "'"
}

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 found"
  else
    fail "$1 is not installed"
  fi
}

echo "==> Doctor (mode: $MODE)"

case "$MODE" in
  dev|test|prod) ;;
  *) echo "Unknown mode '$MODE' (expected dev, test or prod)" >&2; exit 2 ;;
esac

check_command uv
check_command python3
if [ "$MODE" = "test" ] || [ "$MODE" = "dev" ]; then
  if command -v node >/dev/null 2>&1; then
    ok "node found ($(node --version))"
  else
    fail "node is required for JavaScript tests"
  fi
fi

if [ "$MODE" = "test" ]; then
  echo ""
  [ "$FAILURES" -eq 0 ] && echo "Doctor: no failures." || echo "Doctor: $FAILURES failure(s), $WARNINGS warning(s)."
  exit "$([ "$FAILURES" -eq 0 ] && echo 0 || echo 1)"
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not installed"
elif ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not accessible (add your user to the docker group)"
else
  ok "Docker daemon reachable"
  if docker compose version >/dev/null 2>&1; then
    ok "docker compose found"
  else
    fail "docker compose plugin is not installed"
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  fail "$ENV_FILE is missing (run: make setup)"
else
  ok "$ENV_FILE found"
fi

if [ -f "$ENV_FILE" ]; then
  SECRET="$(get_value DJANGO_SECRET_KEY)"
  DEBUG="$(get_value DJANGO_DEBUG)"
  HOSTS="$(get_value DJANGO_ALLOWED_HOSTS)"
  DB_PASSWORD="$(get_value DB_PASSWORD)"
  IMAGEKIT_PUBLIC="$(get_value IMAGEKIT_PUBLIC_KEY)"
  IMAGEKIT_PRIVATE="$(get_value IMAGEKIT_PRIVATE_KEY)"

  if [ "$MODE" = "prod" ]; then
    [ "$DEBUG" = "False" ] || [ "$DEBUG" = "false" ] && ok "DJANGO_DEBUG is False" || fail "DJANGO_DEBUG must be False in production"
    if [ -z "$SECRET" ] || [ "$SECRET" = "django-insecure-dev-only-key-do-not-use-in-production" ]; then
      fail "DJANGO_SECRET_KEY must be set to a production secret"
    else
      ok "DJANGO_SECRET_KEY is set"
    fi
    if [ -z "$HOSTS" ] || [ "$HOSTS" = "localhost,127.0.0.1" ]; then
      fail "DJANGO_ALLOWED_HOSTS must contain the production host"
    else
      ok "DJANGO_ALLOWED_HOSTS is set"
    fi
    if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "devpassword" ]; then
      fail "DB_PASSWORD must not use the development password"
    else
      ok "DB_PASSWORD is set"
    fi
    if [ -z "$IMAGEKIT_PUBLIC" ] || [ -z "$IMAGEKIT_PRIVATE" ]; then
      fail "ImageKit keys are required in production"
    else
      ok "ImageKit keys are set"
    fi
  else
    [ -n "$SECRET" ] && ok "DJANGO_SECRET_KEY is set" || warn "DJANGO_SECRET_KEY is empty (make setup generates one)"
    [ -n "$IMAGEKIT_PUBLIC" ] && [ -n "$IMAGEKIT_PRIVATE" ] \
      && ok "ImageKit keys are set" \
      || warn "ImageKit keys are empty; uploads will fail"
  fi
fi

if [ -d backend/.venv ]; then
  warn "backend/.venv exists; this project uses the root .venv only"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && [ -f "$ENV_FILE" ]; then
  if docker compose --env-file "$ENV_FILE" config -q >/dev/null 2>&1; then
    ok "docker compose configuration is valid"
  else
    fail "docker compose configuration is invalid"
  fi

  if docker compose --env-file "$ENV_FILE" ps --status running --services 2>/dev/null | grep -qx clamav; then
    if docker compose --env-file "$ENV_FILE" exec -T clamav clamdscan --ping 1 >/dev/null 2>&1; then
      ok "ClamAV is responding"
    else
      warn "ClamAV is running but not ready yet"
    fi
  else
    warn "ClamAV is not running (make infra-up)"
  fi
fi

echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo "Doctor: no failures, $WARNINGS warning(s)."
  exit 0
fi
echo "Doctor: $FAILURES failure(s), $WARNINGS warning(s)."
exit 1
