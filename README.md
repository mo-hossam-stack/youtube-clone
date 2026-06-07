# YouTube Clone

> A full-featured video sharing platform with HLS adaptive streaming, authentication, and social engagement — built with Django.

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![ImageKit](https://img.shields.io/badge/CDN-ImageKit-00A7FF)](https://imagekit.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Features

###  Video Management
- **Upload** videos with title, description, and optional custom thumbnail
- **COre** file size limit with MIME type validation (mp4, webm, mov, avi)
- **Delete** your own videos with confirmation dialog

###  Adaptive Streaming
- **HLS.js** powered adaptive bitrate streaming (240p → 1080p)
- Automatic fallback to optimized progressive video
- CDN-delivered via ImageKit SDK with quality optimization (`tr=q-50,f-auto`)

###  Thumbnails & Watermarking
- Auto-generated thumbnails with **dynamic username watermark**
- Custom thumbnails via ImageKit URL transformations
- No server-side image processing — all done on the CDN

###  Engagement
- **Like / Dislike** system with toggle (click again to remove)
- Real-time vote count updates via Fetch API
- **View counting** on every video playback

###  Authentication
- User registration & login with Django's built-in auth
- Authenticated-only uploads and voting
- Smart redirect rules (authenticated users skip login pages)

###  UI/UX
- **Dark theme** with YouTube-inspired red accents
- Responsive video grid layout
- Channel pages with avatar (first-letter + gradient)
- Smooth hover effects, sticky navbar, flash messages

---

## Tech Stack

| Layer              | Technology                                      |
| ------------------ | ----------------------------------------------- |
| **Language**       | Python 3.13                                     |
| **Framework**      | Django 6.0                                      |
| **Database**       | SQLite (development)                            |
| **Templating**     | Django Template Language                        |
| **Frontend**       | HTML5, CSS3 (custom properties), Vanilla JS     |
| **Video CDN**      | ImageKit (upload, HLS, thumbnails, transforms)  |
| **Video Player**   | HLS.js with progressive fallback                |
| **Package Manager**| uv                                              |
| **Validation**     | python-magic (MIME detection)                   |

---


## Architecture

```
┌──────────┐     ┌──────────────┐     ┌───────────┐
│  Browser │────▶│  Django MTV  │────▶│  SQLite   │
│  (HLS.js)│     │  Views/URLs  │     │  Database │
└──────────┘     └──────┬───────┘     └───────────┘
                        │
                ┌───────▼────────┐
                │  ImageKit CDN  │
                │ (videos, HLS,  │
                │  thumbnails)   │
                └────────────────┘
```

Videos and thumbnails are uploaded directly to ImageKit via their API — not stored on the local filesystem. This provides built-in CDN delivery, HLS adaptive streaming, automatic thumbnail generation, and URL-based transformations (optimization, watermarking).

**Watermarking** is applied dynamically via ImageKit URL parameters (`l-text`, `lfo-bottom_left`) — no pre-processed images are stored.

---

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- ImageKit account (free tier works)

### Setup

```bash
# Clone the repository
git clone https://github.com/mo-hossam-stack/youtube-clone.git
cd youtube-clone

# Install dependencies
uv sync

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your ImageKit credentials:
#   IMAGEKIT_PUBLIC_KEY="your_public_key"
#   IMAGEKIT_PRIVATE_KEY="your_private_key"

# Apply database migrations
cd backend && python manage.py makemigrations && python manage.py migrate

# Start the development server
python manage.py runserver
```

Visit **http://127.0.0.1:8000** in your browser.

---



## Development

### Commands

```bash
cd backend
python manage.py runserver          # Start dev server
python manage.py makemigrations     # Create migrations
python manage.py migrate            # Apply migrations
python manage.py createsuperuser    # Create admin
python manage.py test               # Run tests
```

### Environment Variables

| Variable              | Description              |
| --------------------- | ------------------------ |
| `IMAGEKIT_PUBLIC_KEY` | ImageKit API public key  |
| `IMAGEKIT_PRIVATE_KEY`| ImageKit API private key |


---

## Roadmap

- [ ] Search functionality
- [ ] Comments & replies
- [ ] Subscriptions & feed
- [ ] Playlists
- [ ] User profiles & settings
- [ ] Docker deployment
- [ ] CI/CD pipeline
- [ ] Tests

---
