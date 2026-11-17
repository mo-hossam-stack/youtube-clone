# Data Model

Back to [README](../README.md) · [Architecture](architecture.md)

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

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Denormalized like/dislike counts** | Every vote page would require a `COUNT(*)` on the join table. For a page with 50K likes, that's an expensive scan. Storing counts on the `Video` row means reads are O(1). The cost: a tiny window of inconsistency if a vote is deleted mid-request. Acceptable for social features. |
| **`unique_together` on votes** | Prevents double-voting at the database level — no application-level checks needed. A user can like, dislike, or remove their vote, but never hold two votes on one video. |
| **`file_id` as a CDN reference** | The CDN assigns a unique ID to each uploaded file. Storing this allows future operations (delete, regenerate thumbnails, update transforms) without re-uploading. |
| **Watermark as a computed property** | The `display_thumbnail_url` property dynamically appends watermark transformations to the CDN URL. No storage cost, no pre-processing, no cache invalidation. Change the watermark → all thumbnails update instantly. |
| **Property-based computed URLs** | `streaming_url`, `optimized_url`, `generated_thumbnail_url` — these are not stored in the database. They're computed at access time from the base `video_url`. This means if the CDN changes its URL scheme, only the property changes; the database stays untouched. |
