// Exact pixel dimensions + safe margins per Instagram format.
// These are the true render sizes used later by the Playwright screenshot pass.

export type InstagramFormat = "portrait" | "square" | "story";

export const FORMATS: Record<
  InstagramFormat,
  { width: number; height: number; safeMargin: number; label: string }
> = {
  portrait: { width: 1080, height: 1350, safeMargin: 84, label: "Portrait 1080×1350" },
  square: { width: 1080, height: 1080, safeMargin: 72, label: "Square 1080×1080" },
  story: { width: 1080, height: 1920, safeMargin: 120, label: "Story 1080×1920" },
};
