# ETHIOTIMES — Brand & Post Design Guidelines

> Ethiopian News Intelligence, published with international editorial quality.

ETHIOTIMES is a **News Intelligence Engine first**. Instagram is the first
distribution channel; Telegram, X, Facebook, TikTok, and a website follow. This
document defines the visual DNA that keeps every ETHIOTIMES post recognizable,
premium, and credible across formats.

The design language is **editorial, not clickbait**. Think Bloomberg Terminal ×
a contemporary Ethiopian art magazine — dense, confident typography; deliberate
negative space; restraint with color. Never Canva-template energy, never
gradient-soup SaaS, never sensational red arrows.

---

## 1. Brand personality

- **Modern & premium** — magazine-grade composition and typography.
- **Cinematic & contemporary** — strong imagery, dramatic contrast, depth.
- **Ethiopian & international** — rooted in Ethiopian identity, globally legible.
- **Trustworthy** — clear sourcing, no hype, factual tone.

Voice: measured, authoritative, concise. Headlines state; they do not shout.

---

## 2. Color palette

The palette is intentionally narrow: near-black ink backgrounds, crisp off-white
type, and a **single** accent used sparingly (for the category pill, a rule, or
the wordmark tick — never large fills).

| Token | Hex | Usage |
|-------|-----|-------|
| `ink.900` | `#0B0C0E` | Primary background (charcoal/ink) |
| `ink.800` | `#131519` | Elevated surfaces, cards |
| `ink.700` | `#1C1F24` | Borders, dividers on dark |
| `paper.50` | `#F7F6F2` | Primary type (crisp off-white) |
| `paper.300` | `#C9C7BF` | Secondary type, dek |
| `paper.500` | `#8A897F` | Tertiary / captions / source line |
| `accent.green` | `#1FA35A` | Ethiopian-inspired green (primary accent) |
| `accent.gold` | `#D4A24E` | Gold alternate accent (use one accent per post) |
| `signal.red` | `#C2483B` | Reserved for "breaking" only; use rarely |

**Rules**
- One accent per post. Green is the default; gold is the premium/feature alt.
- Accent covers < ~8% of the canvas. Never a full-bleed accent background.
- Maintain WCAG AA contrast for all body text over ink backgrounds.

---

## 3. Typography

Editorial hierarchy is the backbone of the brand.

- **Display / Headline:** a high-contrast serif (e.g. *Fraunces*, *Playfair
  Display*, or *Canela*). Tight leading, large sizes, sentence case.
- **Dek / Body:** a clean grotesque sans (e.g. *Inter*, *Söhne*, *Neue
  Haas Grotesk*). Comfortable leading, restrained weight.
- **Labels / Pills / Source:** the same sans, uppercase, tracked-out
  (letter-spacing ~0.08em), small.

Scale (portrait 1080×1350 reference):

| Role | Size (px) | Weight | Notes |
|------|-----------|--------|-------|
| Category pill | 28 | 600 | Uppercase, tracked |
| Headline | 92–120 | 600 serif | 2–4 lines max |
| Dek | 40 | 400 sans | 1–2 sentences |
| Source footer | 28 | 500 | `SOURCE · ETHIOTIMES` |
| Wordmark | 30 | 700 | Bottom-anchored |

---

## 4. Post layout conventions (consistent across all formats)

Every ETHIOTIMES post, regardless of size, contains these elements in this
z-order and reading order:

1. **Category pill** — top-left, accent outline or subtle fill.
2. **Bold headline** — the anchor; dominant optical weight.
3. **Short dek** — one or two sentences of context.
4. **Source attribution footer** — `Reported by <SOURCE>` + timestamp/date.
5. **ETHIOTIMES wordmark** — bottom, with a small accent tick.

Supporting conventions:
- Consistent **safe margins** (see tokens) so nothing is clipped by platform UI.
- Optional **image zone** (cinematic photo/illustration) with an ink gradient
  scrim so type stays legible.
- A thin **accent rule** may separate headline from footer.

### Formats

| Format | Dimensions | Primary use |
|--------|------------|-------------|
| Portrait | **1080 × 1350** | Default feed post (highest reach) |
| Square | **1080 × 1080** | Grid consistency, carousels |
| Story | **1080 × 1920** | Stories / Reels covers |

Composition stubs for later Playwright screenshotting live in
`frontend/src/templates/instagram/` and are documented in
[`docs/instagram-templates.md`](./instagram-templates.md).

---

## 5. Visual styles (for the later Visual Director)

Phase 1 documents these named styles so the Visual Director (a later phase) can
select and prompt image generation consistently. Each has a one-line intent and
art-direction cues.

1. **Cinematic Editorial** — dramatic lighting, shallow depth of field, filmic
   grade; feels like a still from a documentary film.
2. **Ethiopian Futurism** — Afrofuturist motifs, Ethiopian textile/script
   patterns reinterpreted with modern, speculative technology and materials.
3. **Premium Magazine** — clean studio composition, generous negative space,
   fashion/business-magazine cover energy.
4. **Documentary-Inspired** — candid, photojournalistic, natural light,
   on-the-ground authenticity; minimal manipulation.
5. **Conceptual Editorial** — a single strong metaphor/idea rendered simply;
   op-ed / essay illustration sensibility.
6. **Architectural** — structure, geometry, scale; Addis skylines, GERD,
   infrastructure; strong lines and perspective.
7. **Data-Inspired** — elegant data visualization as art; charts, isotypes, and
   numerals as the hero; restrained palette.
8. **Cultural Contemporary** — modern Ethiopian culture, art, music, fashion,
   and daily life; vibrant but tasteful.

Each style must still respect the palette, type, and layout conventions above —
style affects the **image zone and grade**, not the editorial furniture.

---

## 6. Do / Don't

**Do**
- Keep one clear message per post.
- Let the headline breathe; prefer fewer words.
- Attribute the original source clearly and honestly.
- Use the accent as a scalpel, not a paintbrush.

**Don't**
- No clickbait, ALL-CAPS screaming, or manipulative arrows/emojis.
- No rainbow gradients or drop-shadow stacks.
- No fabricated quotes, imagery misrepresenting events, or fake "verified" marks.
- No more than one accent color per post.

---

## 7. Integrity & sourcing

ETHIOTIMES publishes *intelligence*, so credibility is the brand.

- Always show the reporting source in the footer.
- Never present AI-generated imagery as a photograph of a real event; conceptual
  imagery must read as illustration.
- Telegram-origin sourcing must be verified (see impersonation warning in
  [`docs/architecture.md`](./architecture.md)) before it appears in a post.
