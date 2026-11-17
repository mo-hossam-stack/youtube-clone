# User Workflows

Back to [README](../README.md) · [Architecture](architecture.md)

## 1. Discovery → Watch

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

## 2. Viewer → Creator

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

## 3. Engagement Loop

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

## 4. Content Ownership

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
