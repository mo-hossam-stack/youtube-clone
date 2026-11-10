#!/usr/bin/env bash
# Create backend/.env from the example and fill blank local-development values.
# Never overwrites a non-empty value, so existing secrets are preserved.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_FILE="${1:-backend/.env}"
EXAMPLE_FILE="backend/.env.example"

get_value() {
  sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null \
    | head -n1 \
    | sed -E 's/[[:space:]]+#.*$//' \
    | tr -d '"' \
    | tr -d "'"
}

set_if_empty() {
  local key="$1" value="$2" current
  current="$(get_value "$key")"
  [ -n "$current" ] && return 0

  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    # Avoid gluing the new key onto a final line that has no trailing newline.
    if [ -s "$ENV_FILE" ] && [ -n "$(tail -c 1 "$ENV_FILE")" ]; then
      printf '\n' >> "$ENV_FILE"
    fi
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

if [ ! -f "$ENV_FILE" ]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "==> Created $ENV_FILE from $EXAMPLE_FILE"
fi

SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
DB_PASSWORD="$(get_value DB_PASSWORD)"
DB_PASSWORD="${DB_PASSWORD:-devpassword}"

set_if_empty DJANGO_SECRET_KEY "$SECRET"
set_if_empty DJANGO_DEBUG "True"
set_if_empty DJANGO_ALLOWED_HOSTS "localhost,127.0.0.1"
set_if_empty CSRF_TRUSTED_ORIGINS "http://localhost:8000"
set_if_empty DB_PASSWORD "$DB_PASSWORD"
set_if_empty DATABASE_URL "postgres://vplatform:${DB_PASSWORD}@127.0.0.1:5432/vplatform"
set_if_empty REDIS_URL "redis://127.0.0.1:6379/0"
set_if_empty CELERY_BROKER_URL "redis://127.0.0.1:6379/1"
set_if_empty CELERY_RESULT_BACKEND "redis://127.0.0.1:6379/2"
set_if_empty CLAMAV_HOST "127.0.0.1"
set_if_empty CLAMAV_PORT "3310"
set_if_empty WEB_CONCURRENCY "2"
set_if_empty LOG_LEVEL "INFO"

if [ -z "$(get_value IMAGEKIT_PUBLIC_KEY)" ] || [ -z "$(get_value IMAGEKIT_PRIVATE_KEY)" ]; then
  echo "==> Warning: ImageKit keys are empty. Uploads will fail until you fill them in $ENV_FILE"
fi
