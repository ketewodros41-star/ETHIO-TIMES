# Instagram Theme Deep Specifications

This document outlines the deep-spec implementation details for the production-ready Instagram templates.

## `verified_brief`
Evidenced news brief — confirmed event with primary sources.

### Format Dimensions
- **Portrait**: 1080×1350, Safe Margin: 84px
- **Square**: 1080×1080, Safe Margin: 72px
- **Story**: 1080×1920, Safe Margin: 120px

### Typography Scale
- **Headline**: Portrait: 104px, Square: 84px, Story: 90px (Display font, 600 weight)
- **Dek**: 38px (Sans font, 1.35 line height)
- **Pill**: 26px (Sans font, 600 weight, 0.10em letter spacing, uppercase)
- **Footer**: 26px (Sans font, 0.08em letter spacing, uppercase)

### Color System
- **Background**: Ink 900 (`#0B0C0E`)
- **Accent**: Green (`#1FA35A`)
- **Text**: Primary: Paper 50 (`#F7F6F2`), Secondary: Paper 300 (`#C9C7BF`), Tertiary/Footer: Paper 500 (`#8A897F`)

### Layout Constraints
- EVIDENCED label rules: Must use text only, NO checkmarks. Green accent color.
- Elements flow from top to bottom within the content block, which sits at the bottom of the canvas (justifyContent: flex-end).
- The background image zone is covered by an ink gradient scrim (`linear-gradient(180deg, rgba(11,12,14,0.25) 0%, rgba(11,12,14,0.65) 50%, #0B0C0E 100%)`).

---

## `breaking`
Breaking news — signal red FlashBar, high urgency.

### Format Dimensions
- **Portrait**: 1080×1350, Safe Margin: 84px
- **Square**: 1080×1080, Safe Margin: 72px
- **Story**: 1080×1920, Safe Margin: 120px

### Typography Scale
- **Headline**: Portrait: 116px, Square: 92px, Story: 100px (Display font, 600 weight)
- **Pill**: 26px (Sans font, 600 weight, 0.10em letter spacing, uppercase)
- **FlashBar**: 30px (Sans font, 700 weight, 0.06em letter spacing, uppercase)
- **Footer**: 26px (Sans font, 0.08em letter spacing, uppercase)

### Color System
- **Background**: Ink 900 (`#0B0C0E`)
- **Accent**: Signal Red (`#C2483B`)
- **Text**: Primary: Paper 50 (`#F7F6F2`), FlashBar Text: White (`#FFFFFF`)

### Layout Constraints
- NO Dek used in this template; the headline carries the full weight.
- Red accent color ONLY for Breaking template.
- Full-width FlashBar spanning the top edge of the content area.
- Content is spaced using `justifyContent: space-between` to separate the FlashBar and bottom content.
