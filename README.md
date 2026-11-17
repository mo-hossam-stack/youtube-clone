<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.13+" />
  <img src="https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 6.0" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL 16" />
  <img src="https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis 7" />
  <img src="https://img.shields.io/badge/Celery-5-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery 5" />
  <img src="https://img.shields.io/badge/ImageKit-CDN-00A7FF?style=for-the-badge" alt="ImageKit CDN" />
  <img src="https://img.shields.io/badge/HLS.js-Adaptive%20Streaming-F28D1A?style=for-the-badge" alt="HLS.js" />
  <img src="https://img.shields.io/badge/ClamAV-Antivirus-1A8E5C?style=for-the-badge" alt="ClamAV" />
  <img src="https://img.shields.io/badge/Gunicorn-WSGI-499848?style=for-the-badge&logo=gunicorn&logoColor=white" alt="Gunicorn" />
  <img src="https://img.shields.io/badge/Nginx-Proxy-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="Nginx" />
  <img src="https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
</p>

# YOUTUBE-CLONE

**A video sharing platform engineered for scale — from adaptive streaming to social engagement.**

Upload. Watch. Share. Engage. A production-grade media platform that handles the full content lifecycle: ingestion, transcoding, delivery, watermarking, and community interaction — all without storing a single video file on the application server.

## Quick Start

Prerequisites: [uv](https://docs.astral.sh/uv/) (Python 3.13), Docker with Compose, Node.js 20+, GNU Make.

```bash
git clone https://github.com/mo-hossam-stack/youtube-clone.git
cd youtube-clone
make setup          # env, dependencies, migrations (idempotent)
# add your ImageKit keys to backend/.env
make run
```

The app is at **http://localhost:8000**. First run: ClamAV downloads its virus
signature database (takes a few minutes). Follow with `make logs`, stop with
`make down`. Prefer a lighter loop? `make dev-lite` runs Django on SQLite with
eager Celery and only ClamAV from Docker.

Full instructions and every make target: [docs/development.md](docs/development.md).

## Documentation

| Doc | Contents |
|---|---|
| [Architecture](docs/architecture.md) | The three-layer design (client → Django → CDN → database), why media is decoupled from logic |
| [Data Model](docs/data-model.md) | Entities, relationships, and the reasoning behind counters, votes and computed URLs |
| [Engineering Decisions](docs/decisions.md) | The trade-offs: CDN-first media, URL watermarking, HLS fallback, SSR vs SPA, validation pipeline |
| [User Workflows](docs/workflows.md) | Discovery → watch, upload pipeline, engagement loop, content ownership |
| [UI Design](docs/ui.md) | Component choices and responsive behavior |
| [Development Guide](docs/development.md) | Prerequisites, setup, all make targets, manual start, environment variables |

## The Bottom Line

This project is not a tutorial. It's a **deliberately engineered** video platform built on first principles: decouple media from logic, optimize for reads, design for failure, and never let tools dictate architecture.

Every decision — from the three-layer architecture to the denormalized counters to the URL-level watermarking — exists to answer one question: *how do we deliver video at scale without compromising on user experience or engineering simplicity?*
