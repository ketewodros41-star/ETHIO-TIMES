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
    amharicPoster: "var(--font-ethiopic, 'Noto Sans Ethiopic', 'Nyala', 'Abyssinica SIL', sans-serif)",
    amharicSans: "var(--font-ethiopic, 'Noto Sans Ethiopic', 'Nyala', 'Abyssinica SIL', sans-serif)",
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

export interface HighlightColorToken {
  id: string;
  name: string;
  hex: string;
  category: string;
  mood: string;
}

export const HIGHLIGHT_PALETTES: readonly HighlightColorToken[] = [
  {
    id: "hyper_cyan",
    name: "Hyper Cyan",
    hex: "#00F0FF",
    category: "Broadcast Core",
    mood: "Electric breaking alerts, tech & contemporary data",
  },
  {
    id: "volt_citron",
    name: "Volt Citron",
    hex: "#D4FF00",
    category: "Urgent Scoop",
    mood: "High-energy scoops, athletic milestones & kinetic urgency",
  },
  {
    id: "solar_amber",
    name: "Solar Amber",
    hex: "#FFB800",
    category: "Macro Economy",
    mood: "Central bank directives, trade accords & macroeconomic shifts",
  },
  {
    id: "hyper_coral",
    name: "Hyper Coral",
    hex: "#FF385C",
    category: "Critical Alert",
    mood: "Security emergencies, regional flashpoints & red-hot alerts",
  },
  {
    id: "luminous_mint",
    name: "Luminous Mint",
    hex: "#00F5A0",
    category: "Green & Growth",
    mood: "Agriculture, clean energy & industrial milestones",
  },
  {
    id: "electric_tangerine",
    name: "Electric Tangerine",
    hex: "#FF6B00",
    category: "Momentum",
    mood: "Transit tariffs, infrastructure & commercial logistics",
  },
  {
    id: "orchid_pulse",
    name: "Orchid Pulse",
    hex: "#FF2E93",
    category: "Icons & Culture",
    mood: "Global sports stars, cultural phenomena & human interest",
  },
  {
    id: "celestial_lavender",
    name: "Celestial Lavender",
    hex: "#B8A4FF",
    category: "Policy & Insight",
    mood: "Diplomatic summits, foreign relations & strategic analysis",
  },
  {
    id: "stark_white",
    name: "Stark White",
    hex: "#FFFFFF",
    category: "Monochrome Pure",
    mood: "Somber investigative dispatches & clean minimalism",
  },
] as const;

export type HighlightColorId = (typeof HIGHLIGHT_PALETTES)[number]["id"];
