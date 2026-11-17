# UI Design

Back to [README](../README.md)

## Component Highlights

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

## Responsive Behavior

```
Grid:  auto-fill, minmax(300px, 1fr)
       → 1 column on narrow screens, 2–3 on tablet, 4+ on desktop

Player: 16:9 aspect ratio, full-width container, max 1000px
        → fills any screen proportionally

Auth forms: max-width 420px, centered
           → never feels stretched on wide screens
```
