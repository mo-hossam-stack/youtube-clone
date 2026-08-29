#!/usr/bin/env bash
# One-command dev runner: starts ClamAV, runs Django runserver, stops ClamAV on exit.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

compose() {
  local -a cmd=(docker compose)
  docker info >/dev/null 2>&1 || cmd=(sudo docker compose)
  "${cmd[@]}" "$@"
}

PYTHON=python
for p in .venv/bin/python backend/.venv/bin/python; do
  if [[ -x "$p" ]]; then PYTHON="$p"; break; fi
done

stop_clamav() {
  echo
  echo "==> Stopping ClamAV..."
  compose stop clamav >/dev/null 2>&1 || true
}
trap stop_clamav EXIT INT TERM

echo "==> Starting ClamAV..."
compose up -d clamav

echo "==> Running: $PYTHON backend/manage.py runserver"
echo "    Ctrl+C to stop (ClamAV stops with it)"
"$PYTHON" backend/manage.py runserver "$@"