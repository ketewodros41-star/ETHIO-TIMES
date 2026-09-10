/**
 * ETHIOTIMES Instagram theme registry.
 *
 * ThemeId is the canonical identifier used in social_posts.theme.
 * 'verified_brief' and 'breaking' are production deep-spec implementations.
 * All others are safe production stubs (correct accent, generic layout).
 */

export type ThemeId =
  | "broadcast_impact"
  | "country_spotlight"
  | "headline_impact"
  | "verified_brief"
  | "breaking"
  | "politics_sensitive"
  | "economy"
  | "data_chart"
  | "official_statement"
  | "quote"
  | "culture_photo";

export interface ThemeMeta {
  id: ThemeId;
  label: string;
  accent: "green" | "gold" | "red";
  description: string;
  implementationStatus: "production" | "stub";
}

export const THEMES: Record<ThemeId, ThemeMeta> = {
  broadcast_impact: {
    id: "broadcast_impact",
    label: "Broadcast Impact (Habesha Style)",
    accent: "green",
    description: "Exact replica of diaspora broadcast post: full-bleed speaker photo, Anton/Impact heavy condensed uppercase headline, cyan punchline, ET hexagon monogram, and downward arrow CTA",
    implementationStatus: "production",
  },
  country_spotlight: {
    id: "country_spotlight",
    label: "Country Spotlight (Flag Badge)",
    accent: "green",
    description: "Circular national flag badge behind subject, Anton poster typography, dual-color headline split, ET monogram, and downward arrow CTA",
    implementationStatus: "production",
  },
  headline_impact: {
    id: "headline_impact",
    label: "Headline Impact",
    accent: "green",
    description: "Mega-scale editorial card with ET brandmark and dual-tone punchline highlight",
    implementationStatus: "production",
  },
  verified_brief: {
    id: "verified_brief",
    label: "Verified Brief",
    accent: "green",
    description: "Evidenced news brief — confirmed event with primary sources",
    implementationStatus: "production",
  },
  breaking: {
    id: "breaking",
    label: "Breaking",
    accent: "red",
    description: "Breaking news — signal red FlashBar, high urgency",
    implementationStatus: "production",
  },
  politics_sensitive: {
    id: "politics_sensitive",
    label: "Politics",
    accent: "gold",
    description: "Political stories — review-gated, amber accent",
    implementationStatus: "stub",
  },
  economy: {
    id: "economy",
    label: "Economy",
    accent: "green",
    description: "Economic & financial news",
    implementationStatus: "stub",
  },
  data_chart: {
    id: "data_chart",
    label: "Data",
    accent: "gold",
    description: "Data-driven visual — statistics and charts",
    implementationStatus: "stub",
  },
  official_statement: {
    id: "official_statement",
    label: "Official",
    accent: "gold",
    description: "Government or institutional statements",
    implementationStatus: "stub",
  },
  quote: {
    id: "quote",
    label: "Quote",
    accent: "green",
    description: "Pull-quote format for key statements",
    implementationStatus: "stub",
  },
  culture_photo: {
    id: "culture_photo",
    label: "Culture",
    accent: "gold",
    description: "Full-bleed cultural and arts coverage",
    implementationStatus: "stub",
  },
};

export const THEME_IDS = Object.keys(THEMES) as ThemeId[];
