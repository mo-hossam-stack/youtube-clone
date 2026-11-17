# Development Guide

Back to [README](../README.md)

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python 3.13 and dependencies
- Docker with the Compose plugin (web, worker, Postgres, Redis, ClamAV)
- Node.js 20+ for the JavaScript tests
- GNU Make

## Setup

```bash
git clone https://github.com/mo-hossam-stack/youtube-clone.git
cd youtube-clone
make setup
```

`make setup` is idempotent. It:

- creates `backend/.env` from the example and generates `DJANGO_SECRET_KEY`
- installs the locked Python dependencies with `uv sync --frozen`
- starts Postgres, Redis and ClamAV in Docker and waits for ClamAV
- applies database migrations
- warns if the ImageKit keys are still empty

Add your ImageKit keys to `backend/.env`, then run `make run` (see README).

> First run: ClamAV downloads its virus signature database (takes a few minutes).

## Make targets

| Target | What it does |
|---|---|
| `make run` | Build and run everything in Docker: Django (gunicorn), Celery worker, Postgres, Redis, ClamAV. Migrations run on container start. |
| `make down` / `logs` / `ps` | Stop containers (volumes kept) / follow logs / show status |
| `make dev-lite` | Django on SQLite with eager Celery and only ClamAV from Docker |
| `make worker` | Run a host Celery worker (requires `make infra-up`) |
| `make migrate` / `makemigrations` | Apply / create database migrations |
| `make shell` / `superuser` | Django shell / create an admin user |
| `make cleanup` | Clean expired quarantine files |
| `make check` | Django checks + migration drift |
| `make test` | Python tests (SQLite/eager) + JavaScript tests |
| `make test-integration` | Real worker/Redis/ClamAV integration test |
| `make doctor` | Diagnose tooling and configuration |
| `make up` | Like `make run`, without auto-creating `backend/.env` |
| `make clean` / `clean-all` | Stop and remove local images / destructive: also delete volumes and dev data |

`make test` needs neither Docker nor ImageKit credentials. `make test-integration`
uses real Postgres, Redis and ClamAV with a real Celery worker and a mocked
ImageKit call.

## Manual start (without Make)

```bash
uv sync --frozen
cp backend/.env.example backend/.env   # Add your ImageKit credentials
docker compose up -d --wait postgres redis clamav
uv run --frozen python backend/manage.py migrate
uv run --frozen python backend/manage.py runserver
```

## Environment variables

See `backend/.env.example` for the full list. The essentials: ImageKit keys
(`IMAGEKIT_*`), `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`,
`CELERY_BROKER_URL`, ClamAV connection settings.
