# ETHIOTIMES — Instagram Template Stubs

These are **composition stubs** for later automated rendering. In a later phase,
a headless browser (Playwright) will load a template route with post data in the
query/props and screenshot it at exact pixel dimensions to produce the final PNG.

Phase 1 deliverable: React composition components + a preview route, using the
shared [design tokens](./design-tokens.json) and the layout conventions in
[brand-guidelines.md](./brand-guidelines.md). No image generation, no Playwright
wiring yet (that is a later phase).

## Components

Located in `frontend/src/templates/instagram/`:

- `PostTemplate.tsx` — shared layout engine (category pill, headline, dek, source
  footer, ETHIOTIMES wordmark, optional image zone + scrim).
- `formats.ts` — exact pixel dimensions + safe margins per format.
- `PortraitPost.tsx` (1080×1350), `SquarePost.tsx` (1080×1080),
  `StoryPost.tsx` (1080×1920) — thin wrappers binding a format to the engine.

## Preview route

`/(studio)/studio/templates` renders all three formats with sample data so a
designer can eyeball them. Because each template renders at true pixel size, the
preview scales them down with CSS transforms for on-screen viewing while keeping
the underlying element at 1:1 for future screenshotting.

## Data contract (`PostTemplateData`)

```ts
type PostTemplateData = {
  category: string;        // e.g. "ECONOMY"
  headline: string;        // 2–4 lines
  dek?: string;            // 1–2 sentences
  source: string;          // original reporting source
  dateLabel?: string;      // e.g. "9 SEP 2026"
  imageUrl?: string;       // optional cinematic image zone
  accent?: "green" | "gold";
  style?: VisualStyle;     // one of the documented visual styles
};
```

## Later (out of Phase 1)

- Playwright screenshot service that renders a template route → PNG at exact size.
- Visual Director selecting a `VisualStyle` and generating the image zone.
- Carousel composition (multi-slide) and per-slide templating.
