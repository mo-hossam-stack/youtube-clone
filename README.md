<picture src="https://img.shields.io/badge/status-production--ready-ff0000?style=for-the-badge&logo=youtube" alt="Status" />
<picture src="https://img.shields.io/badge/build-passing-success?style=for-the-badge&logo=github" alt="Build" />

<br/>

# V Platform

**A video sharing platform engineered for scale — from adaptive streaming to social engagement.**

Upload. Watch. Share. Engage. A production-grade media platform that handles the full content lifecycle: ingestion, transcoding, delivery, watermarking, and community interaction — all without storing a single video file on the application server.

---

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

---

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

### Why This Architecture Works

**Separation of media from logic.** The application server never opens a video file. It never transcodes. It never generates thumbnails. It receives uploads and immediately pushes them to the CDN; thereafter, it only stores *URLs*. This means:

- **The app server stays lean** — no media processing libraries, no file system I/O contention
- **The CDN handles scale** — bandwidth and transcoding are the media pipeline's problem, not the application's
- **Watermarking costs nothing** — it's a URL parameter, not a stored image
- **Adaptive streaming is automatic** — the CDN generates HLS manifests at multiple bitrates on ingest

---

## System Design: Data Model

The data model is intentionally minimal — four core entities that capture the entire content lifecycle.

```
┌─────────────────────┐       ┌─────────────────────────┐
│        User         │       │         Video           │
│─────────────────────│       │─────────────────────────│
│ id (PK)             │──────▶│ id (PK)                 │
│ username            │  ┌───▶│ user_id (FK → User)     │
│ email               │  │    │ title                   │
│ password (hashed)   │  │    │ description             │
└─────────────────────┘  │    │ file_id (CDN reference) │
                         │    │ video_url               │
                         │    │ thumbnail_url            │
                         │    │ views (counter)         │
                         │    │ likes (denormalized)    │
                         │    │ dislikes (denormalized) │
                         │    │ created_at              │
                         │    │ updated_at              │
                         │    └───────────┬─────────────┘
                         │                │
┌─────────────────────┐  │                │
│     VideoLike       │  │                │
│─────────────────────│  │                │
│ id (PK)             │  │                │
│ user_id (FK → User) │──┘                │
│ video_id (FK → Vid) │───────────────────┘
│ value (+1 / -1)     │
│ created_at          │
│─────────────────────│
│ UNIQUE(user, video) │  ← prevents duplicate votes
└─────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Denormalized like/dislike counts** | Every vote page would require a `COUNT(*)` on the join table. For a page with 50K likes, that's an expensive scan. Storing counts on the `Video` row means reads are O(1). The cost: a tiny window of inconsistency if a vote is deleted mid-request. Acceptable for social features. |
| **`unique_together` on votes** | Prevents double-voting at the database level — no application-level checks needed. A user can like, dislike, or remove their vote, but never hold two votes on one video. |
| **`file_id` as a CDN reference** | The CDN assigns a unique ID to each uploaded file. Storing this allows future operations (delete, regenerate thumbnails, update transforms) without re-uploading. |
| **Watermark as a computed property** | The `display_thumbnail_url` property dynamically appends watermark transformations to the CDN URL. No storage cost, no pre-processing, no cache invalidation. Change the watermark → all thumbnails update instantly. |
| **Property-based computed URLs** | `streaming_url`, `optimized_url`, `generated_thumbnail_url` — these are not stored in the database. They're computed at access time from the base `video_url`. This means if the CDN changes its URL scheme, only the property changes; the database stays untouched. |

---

## User Workflows

### 1. Discovery → Watch

```
Visitor arrives ──▶ Home page loads ──▶ Video grid renders
                                              │
                                              ▼
                                    User clicks a card
                                              │
                                              ▼
                              ┌────────────────────────────┐
                              │    HLS Player Initializes   │
                              │                            │
                              │  1. HLS.js tries adaptive   │
                              │     stream (240p→1080p)     │
                              │  2. Falls back to optimized │
                              │     progressive MP4         │
                              │  3. Native HLS on iOS       │
                              └────────────────────────────┘
                                              │
                                              ▼
                              View increments (1 per page load)
                              ──no duplicate counting──
                                              │
                                              ▼
                              User sees: title, description,
                              channel link, like/dislike UI,
                              view count, upload date
```

### 2. Viewer → Creator

```
Register ──▶ Auto-login ──▶ Redirect to home
                                │
                                ▼
                        "Upload" button visible
                                │
                                ▼
                  ┌───────────────────────────┐
                  │     Upload Flow            │
                  │                            │
                  │  1. Fill title + desc      │
                  │  2. Select video file      │
                  │  3. (Optional) Custom       │
                  │     thumbnail              │
                  │  4. Submit                 │
                  └───────────┬───────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │    Server-Side Validation     │
              │                              │
              │  • Title: min 3 chars        │
              │  • File extension: mp4,      │
              │    webm, mov, avi            │
              │  • MIME type: magic bytes    │
              │    sniff (not just extension)│
              │  • Size: max 100MB           │
              └───────────┬──────────────────┘
                          │
                          ▼
              ┌──────────────────────────────┐
              │    CDN Media Pipeline         │
              │                              │
              │  1. Upload raw video to CDN  │
              │  2. CDN generates HLS master  │
              │     manifest (240/360/480/    │
              │     720/1080p)               │
              │  3. CDN auto-generates a     │
              │     thumbnail                │
              │  4. Application stores the   │
              │     returned URL + file_id   │
              └───────────┬──────────────────┘
                          │
                          ▼
              ┌──────────────────────────────┐
              │    Zero-byte stored locally   │
              │    Video ready to stream      │
              │    in under 2 seconds         │
              └──────────────────────────────┘
```

### 3. Engagement Loop

```
User watches video
        │
        ▼
   ┌──────────┐     Like (first click)
   │ Vote UI  │──────────────────▶ +1 likes, active state
   │          │
   │ 👍 👎    │     Dislike (second click)
   │          │──────────────────▶ switches to dislike:
   └──────────┘     -1 likes, +1 dislikes, active state

        │
   Remove vote (click active button again)
        │
        ▼
   Toggle off: count reverts, button inactive

        │
        ▼
   Unauthenticated user clicks vote
        │
        ▼
   Redirected to login page
```

### 4. Content Ownership

```
Owner visits their video
        │
        ▼
   Sees "Delete" button (hidden from other users)
        │
        ▼
   Delete flow:
   1. Confirmation dialog ("Are you sure?")
   2. AJAX POST to /<id>/delete/
   3. Server: calls CDN delete API → removes video from CDN
   4. Server: deletes database record
   5. Redirect to home page

        │
        ▼
   Channel page: /channel/<username>/
   Lists every video by that user, newest first
```

---


### Component Highlights

| Component | Design Choice | Why |
|---|---|---|
| **Video Cards** | Border + hover lift (`translateY(-4px)`), red border on hover, dark overlay play icon fades in | Creates a tactile, responsive feel; the red border signals "this is clickable" without cluttering the default state |
| **Navbar** | Sticky, dark secondary background, red brand icon, pill-shaped nav links | Always accessible; the red icon anchors the brand; pill shapes feel modern and friendly |
| **Auth Headers** | Gradient text (white → red) on "Create Account" / "Welcome Back" | Adds personality to an otherwise utilitarian form; the gradient subtly echoes the brand colors |
| **Channel Avatar** | First-letter initial on a red gradient circle, 40px (detail) / 80px (channel header) | Zero-config identity — no avatar upload needed, every channel instantly recognizable |
| **Upload Form** | Dashed dropzone border that turns red on hover, full-page loading overlay with spinner | The red hover signals readiness; the overlay prevents accidental navigation during upload |
| **Empty State** | Large muted emoji icon + heading + description | Turns a "nothing here" moment into a gentle, human message rather than a stark blank page |
| **Vote Buttons** | Pill-shaped, tertiary background, active state fills with red | Clear affordance for clickability; the red active state gives immediate feedback that the action registered |
| **Flash Messages** | Color-coded borders + tinted backgrounds (green/red/blue) | At-a-glance feedback without blocking the user; no intrusive modals |

### Responsive Behavior

```
Grid:  auto-fill, minmax(300px, 1fr)
       → 1 column on narrow screens, 2–3 on tablet, 4+ on desktop

Player: 16:9 aspect ratio, full-width container, max 1000px
        → fills any screen proportionally

Auth forms: max-width 420px, centered
           → never feels stretched on wide screens
```

---

## Engineering Decisions & Trade-offs

### 1. CDN-First Media vs. Local Storage

**Chosen:** Upload directly to CDN; store only URLs.

**Trade-off:** You trade a dependency on an external service (CDN) for a massive reduction in server complexity. No ffmpeg, no file system management, no transcoding queues, no thumbnail generators. The CDN handles:
- Storage at global edge
- Transcoding to multiple bitrates
- HLS packaging
- Thumbnail extraction
- Image optimization (auto-format, quality)
- On-the-fly URL transformations (watermarking, resizing)

If the CDN goes down, uploads stop — but the app server stays up and existing content continues streaming from cache.

### 2. URL-Level Watermarking vs. Pre-Rendered

**Chosen:** Watermark applied via CDN URL transformation parameters (`l-text, lfo-bottom_left, fs-32, co-FFFFFF`).

**Trade-off:** The watermark is not embedded in the pixels — it's a CDN rendering instruction. Benefits: zero storage cost, instant changes (update the URL parameter → all thumbnails update), no pre-processing pipeline. Cost: the watermark is not baked into the file; if someone downloads the raw CDN URL without parameters, they get the unwatermarked version. Acceptable for a social platform (not a DRM system).

### 3. HLS with Progressive Fallback

**Chosen:** Try HLS.js first → fall back to optimized MP4 → native HLS on iOS.

**Trade-off:** HLS delivers adaptive bitrate (critical for mobile and variable connections) but requires JavaScript. The fallback chain ensures every browser gets a playable video. The cost: two CDN URLs per video (HLS manifest + progressive MP4). Storage is cheap; user experience is not.

### 4. Denormalized Engagement Counters

**Chosen:** Store `likes` and `dislikes` as integer columns on the `Video` model alongside a normalized `VideoLike` join table.

**Trade-off:** Two sources of truth that must be kept in sync. Reads are O(1) (no `COUNT(*)`). Writes are more complex (update both the join table and the counter). For a social platform where 99.9% of operations are reads (page loads watching a video), this is the right trade. If counters drift, a background reconciliation job can fix them.

### 5. Server-Side Rendering vs. SPA

**Chosen:** Django MTV (Model-Template-View) with server-rendered HTML and progressive enhancement via vanilla JavaScript.

**Trade-off:** No client-side routing, no React/Gatsby/Next.js complexity. Pages render fast on first load (critical for video discovery SEO). Interactivity (voting, upload, delete) is added via `fetch()` calls that update the DOM. The cost: UI state is not as fluid as a full SPA — navigation triggers full page loads. For a content-consumption platform, this is acceptable and simpler to maintain.

### 6. Upload Validation Pipeline

The upload form validates at **three levels**:
1. **Browser** — `accept="video/*"` attribute prevents non-video file selection
2. **Django form** — extension check + MIME type sniffing via `python-magic` (reads the actual file header bytes, not just the extension) + file size cap
3. **CDN** — the CDN may reject corrupted or unsupported files

This defense-in-depth means a user can't bypass browser validation and send a malicious payload directly to the API.

---




## Quick Start

```bash
git clone https://github.com/mo-hossam-stack/youtube-clone.git
cd youtube-clone
uv sync
cp backend/.env.example backend/.env   # Add your CDN credentials
cd backend && python manage.py makemigrations && python manage.py migrate
python manage.py runserver
```

Visit **http://127.0.0.1:8000** — upload a video, watch it stream with adaptive bitrate, and engage with likes and views.

---

## The Bottom Line

This project is not a tutorial. It's a **deliberately engineered** video platform built on first principles: decouple media from logic, optimize for reads, design for failure, and never let tools dictate architecture.

Every decision — from the three-layer architecture to the denormalized counters to the URL-level watermarking — exists to answer one question: *how do we deliver video at scale without compromising on user experience or engineering simplicity?*
