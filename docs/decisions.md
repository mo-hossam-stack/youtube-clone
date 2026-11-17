# Engineering Decisions & Trade-offs

Back to [README](../README.md) · [Architecture](architecture.md)

## 1. CDN-First Media vs. Local Storage

**Chosen:** Upload directly to CDN; store only URLs.

**Trade-off:** You trade a dependency on an external service (CDN) for a massive reduction in server complexity. No ffmpeg, no file system management, no transcoding queues, no thumbnail generators. The CDN handles:
- Storage at global edge
- Transcoding to multiple bitrates
- HLS packaging
- Thumbnail extraction
- Image optimization (auto-format, quality)
- On-the-fly URL transformations (watermarking, resizing)

If the CDN goes down, uploads stop — but the app server stays up and existing content continues streaming from cache.

## 2. URL-Level Watermarking vs. Pre-Rendered

**Chosen:** Watermark applied via CDN URL transformation parameters (`l-text, lfo-bottom_left, fs-32, co-FFFFFF`).

**Trade-off:** The watermark is not embedded in the pixels — it's a CDN rendering instruction. Benefits: zero storage cost, instant changes (update the URL parameter → all thumbnails update), no pre-processing pipeline. Cost: the watermark is not baked into the file; if someone downloads the raw CDN URL without parameters, they get the unwatermarked version. Acceptable for a social platform (not a DRM system).

## 3. HLS with Progressive Fallback

**Chosen:** Try HLS.js first → fall back to optimized MP4 → native HLS on iOS.

**Trade-off:** HLS delivers adaptive bitrate (critical for mobile and variable connections) but requires JavaScript. The fallback chain ensures every browser gets a playable video. The cost: two CDN URLs per video (HLS manifest + progressive MP4). Storage is cheap; user experience is not.

## 4. Denormalized Engagement Counters

**Chosen:** Store `likes` and `dislikes` as integer columns on the `Video` model alongside a normalized `VideoLike` join table.

**Trade-off:** Two sources of truth that must be kept in sync. Reads are O(1) (no `COUNT(*)`). Writes are more complex (update both the join table and the counter). For a social platform where 99.9% of operations are reads (page loads watching a video), this is the right trade. If counters drift, a background reconciliation job can fix them.

## 5. Server-Side Rendering vs. SPA

**Chosen:** Django MTV (Model-Template-View) with server-rendered HTML and progressive enhancement via vanilla JavaScript.

**Trade-off:** No client-side routing, no React/Gatsby/Next.js complexity. Pages render fast on first load (critical for video discovery SEO). Interactivity (voting, upload, delete) is added via `fetch()` calls that update the DOM. The cost: UI state is not as fluid as a full SPA — navigation triggers full page loads. For a content-consumption platform, this is acceptable and simpler to maintain.

## 6. Upload Validation Pipeline

The upload form validates at **three levels**:
1. **Browser** — `accept="video/*"` attribute prevents non-video file selection
2. **Django form** — extension check + MIME type sniffing via `python-magic` (reads the actual file header bytes, not just the extension) + file size cap
3. **CDN** — the CDN may reject corrupted or unsupported files

This defense-in-depth means a user can't bypass browser validation and send a malicious payload directly to the API.
