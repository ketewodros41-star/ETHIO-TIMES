// Canonical ETHIOTIMES design tokens (mirrors docs/design-tokens.json).
// Used by the Instagram post templates so composition stays on-brand.

export const tokens = {
  color: {
    ink: { 900: "#0B0C0E", 800: "#131519", 700: "#1C1F24", 600: "#262A31" },
    paper: { 50: "#F7F6F2", 300: "#C9C7BF", 500: "#8A897F" },
    accent: { green: "#1FA35A", gold: "#D4A24E", red: "#C2483B" },
    signal: { red: "#C2483B" },
  },
  font: {
    display: "var(--font-display)",
    sans: "var(--font-sans)",
    mono: "var(--font-mono)",
    poster: "var(--font-poster, 'Anton', 'Bebas Neue', 'Barlow Condensed', 'Impact', sans-serif)",
  },
} as const;

export type AccentKey = keyof typeof tokens.color.accent;

export const VISUAL_STYLES = [
  "Cinematic Editorial",
  "Ethiopian Futurism",
  "Premium Magazine",
  "Documentary-Inspired",
  "Conceptual Editorial",
  "Architectural",
  "Data-Inspired",
  "Cultural Contemporary",
] as const;

export type VisualStyle = (typeof VISUAL_STYLES)[number];
