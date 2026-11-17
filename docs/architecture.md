# Architecture

Back to [README](../README.md).

## The Problem

Building a video platform is deceptively hard. The naive approach — storing videos on the application server, serving them directly, generating thumbnails server-side — collapses under real-world constraints:

| Problem | Why It Matters |
|---|---|
| **Video files are huge** | A 5-minute 1080p clip is 200–500 MB. Local storage fills fast; serving it strains the app server. |
| **Not every device plays every format** | Desktop plays MP4 natively. Mobile needs HLS. Smart TVs need adaptive bitrate. One file doesn't fit all. |
| **Uploads fail on flaky connections** | A 400 MB upload lost at 95% destroys user trust and retention. |
| **Content theft is trivial** | Without watermarking, anyone can rehost your creators' content. |
| **Engagement drives retention** | A video without likes, views, and creator identity is a dead page — not a community. |
| **Dual writes kill performance** | If every like/dislike hits both a relational join table *and* a count column, reads slow down as engagement grows. |

## The Solution

A **three-layer architecture** that decouples media operations from application logic:

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│                                                                  │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│   │  Video Grid  │  │  HLS Player  │  │  Auth / Upload / Vote │  │
│   │  (Responsive)│  │  (Adaptive)  │  │  (Vanilla JS + Fetch)│  │
│   └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘  │
│          │                 │                       │              │
│          └─────────────────┼───────────────────────┘              │
│                            │  HTTP / AJAX                         │
└────────────────────────────┼──────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────┐
│                    APPLICATION LAYER                              │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │                   Django Server (MTV)                     │    │
│   │                                                          │    │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │    │
│   │  │ Accounts │  │  Videos  │  │  Config  │               │    │
│   │  │  (Auth)  │  │ (Core)   │  │  (Routes)│               │    │
│   │  └──────────┘  └──────────┘  └──────────┘               │    │
│   │                                                          │    │
│   │  ┌──────────────────────────────────────────────────┐    │    │
│   │  │  Responsibilities:                               │    │    │
│   │  │  • Authentication & session management           │    │    │
│   │  │  • Request validation (MIME, size, title)        │    │    │
│   │  │  • Business logic (voting, view counting)        │    │    │
│   │  │  • URL routing & template rendering              │    │    │
│   │  │  • Orchestrating the media pipeline              │    │    │
│   │  └──────────────────────────────────────────────────┘    │    │
│   └──────────────────────────────────────────────────────────┘    │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────┐
│                    MEDIA PIPELINE LAYER                            │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │              Cloud Media Delivery Network                 │    │
│   │                                                          │    │
│   │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │    │
│   │  │  Upload API │  │  Storage   │  │  Transcoding     │   │    │
│   │  │  (Direct)   │──▶│  (CDN)    │──▶│  (HLS, Thumbnail)│   │    │
│   │  └────────────┘  └────────────┘  └──────────────────┘   │    │
│   │                                        │                 │    │
│   │  ┌──────────────────────────────────────┘                 │    │
│   │  │                                                       │    │
│   │  │  ┌──────────────────┐  ┌──────────────────────────┐   │    │
│   │  │  │  Adaptive HLS    │  │  On-the-fly Watermarking │   │    │
│   │  │  │  240p → 1080p    │  │  (URL-level transform)   │   │    │
│   │  │  └──────────────────┘  └──────────────────────────┘   │    │
│   │                                                          │    │
│   │  Key advantage: Zero bytes stored on the application     │    │
│   │  server. All media operations happen at the CDN edge.    │    │
│   └──────────────────────────────────────────────────────────┘    │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────┐
│                     DATA LAYER                                    │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │                    Relational Database                     │    │
│   │                                                          │    │
│   │  • Users & authentication (Django auth built-in)         │    │
│   │  • Video metadata (title, description, URLs, counts)     │    │
│   │  • Social graph (likes/dislikes with integrity)          │    │
│   │  • Foreign key relationships for content ownership       │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│   SQLite (dev) → PostgreSQL (prod) — schema is portable.         │
└──────────────────────────────────────────────────────────────────┘
```

## Why This Architecture Works

**Separation of media from logic.** The application server never opens a video file. It never transcodes. It never generates thumbnails. It receives uploads and immediately pushes them to the CDN; thereafter, it only stores *URLs*. This means:

- **The app server stays lean** — no media processing libraries, no file system I/O contention
- **The CDN handles scale** — bandwidth and transcoding are the media pipeline's problem, not the application's
- **Watermarking costs nothing** — it's a URL parameter, not a stored image
- **Adaptive streaming is automatic** — the CDN generates HLS manifests at multiple bitrates on ingest

Related: [Data Model](data-model.md) · [Engineering Decisions](decisions.md) · [User Workflows](workflows.md)
