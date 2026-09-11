/**
 * ETHIOTIMES Instagram post primitives.
 *
 * All inline styles — Playwright screenshots these components directly.
 * Never use Tailwind classes inside this file.
 */
import { tokens } from "@/lib/design-tokens";

/** Helper to detect Ge'ez / Ethiopic Unicode characters */
export function isEthiopic(text?: string | null): boolean {
  if (!text) return false;
  return /[\u1200-\u137F\u1380-\u139F\u2D80-\u2DDF\uAB00-\uAB2F]/.test(text);
}

interface AccentProps {
  accent?: string;
}

/** Category pill — outlined, uppercase, small caps */
export function Pill({ children, accent = tokens.color.accent.green }: AccentProps & { children: React.ReactNode }) {
  const textContent = typeof children === "string" ? children : "";
  const ethiopic = isEthiopic(textContent);
  return (
    <span style={{
      display: "inline-block",
      border: `2px solid ${accent}`,
      color: accent,
      borderRadius: 999,
      padding: "10px 24px",
      fontSize: 26,
      fontWeight: 600,
      letterSpacing: ethiopic ? "0.02em" : "0.10em",
      textTransform: ethiopic ? "none" : ("uppercase" as const),
      fontFamily: ethiopic ? tokens.font.amharicSans : tokens.font.sans,
    }}>
      {children}
    </span>
  );
}

/** Display headline */
export function Headline({ children, size = 104 }: { children: React.ReactNode; size?: number }) {
  const textContent = typeof children === "string" ? children : "";
  const ethiopic = isEthiopic(textContent);
  return (
    <h1 style={{
      fontFamily: ethiopic ? tokens.font.amharicPoster : tokens.font.display,
      fontWeight: ethiopic ? 900 : 600,
      fontSize: ethiopic ? Math.round(size * 0.94) : size,
      lineHeight: ethiopic ? 1.15 : 1.02,
      letterSpacing: ethiopic ? "0em" : "-0.01em",
      margin: "28px 0 0",
      maxWidth: "94%",
      color: tokens.color.paper[50],
      wordBreak: "break-word",
    }}>
      {children}
    </h1>
  );
}

/** Deck / subheadline */
export function Dek({ children }: { children: React.ReactNode }) {
  const textContent = typeof children === "string" ? children : "";
  const ethiopic = isEthiopic(textContent);
  return (
    <p style={{
      fontSize: 38,
      lineHeight: ethiopic ? 1.48 : 1.35,
      color: tokens.color.paper[300],
      margin: "22px 0 0",
      maxWidth: "88%",
      fontFamily: ethiopic ? tokens.font.amharicSans : tokens.font.sans,
      letterSpacing: ethiopic ? "0.01em" : "normal",
    }}>
      {children}
    </p>
  );
}

/** Horizontal accent rule */
export function Rule({ accent = tokens.color.accent.green }: AccentProps) {
  return (
    <div style={{
      height: 2,
      width: 96,
      backgroundColor: accent,
      margin: "36px 0 24px",
    }} />
  );
}

/** ETHIOPIAN TIMES wordmark with ET geometric monogram badge */
export function Wordmark({ accent = tokens.color.accent.green }: AccentProps) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 14,
      fontFamily: tokens.font.display,
      fontWeight: 800,
      color: tokens.color.paper[50],
      textTransform: "uppercase" as const,
    }}>
      <svg
        width="44"
        height="44"
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        <polygon
          points="50,6 88,28 88,72 50,94 12,72 12,28"
          stroke="#FFFFFF"
          strokeWidth="6.5"
          strokeLinejoin="round"
          fill="none"
        />
        <path
          d="M32 32 H47 M32 50 H44 M32 68 H47 M32 32 V68"
          stroke="#FFFFFF"
          strokeWidth="6"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
        <path
          d="M52 32 H78 M65 32 V68"
          stroke="#FFFFFF"
          strokeWidth="6"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
        <circle cx="77" cy="68" r="3.2" fill={accent} />
      </svg>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 0.92, textAlign: "left" as const }}>
        <span style={{ fontSize: 24, fontWeight: 900, letterSpacing: "0.06em", color: tokens.color.paper[50] }}>
          ETHIOPIAN
        </span>
        <span style={{ fontSize: 24, fontWeight: 900, letterSpacing: "0.06em", color: tokens.color.paper[300] }}>
          TIMES<span style={{ color: accent }}>.</span>
        </span>
      </div>
    </div>
  );
}

/** Source + date footer line */
export function Footer({
  source,
  date,
  accent = tokens.color.accent.green,
}: {
  source: string;
  date?: string;
  accent?: string;
}) {
  return (
    <div style={{ fontSize: 26, color: tokens.color.paper[500], fontFamily: tokens.font.sans }}>
      <div style={{ textTransform: "uppercase" as const, letterSpacing: "0.08em" }}>
        {source}
      </div>
      {date && <div style={{ marginTop: 4 }}>{date}</div>}
    </div>
  );
}

/** Ink gradient scrim over image zone — subtle top/mid transparency to preserve 4K brilliance, dark bottom for headline contrast */
export function Scrim() {
  return (
    <div style={{
      position: "absolute" as const,
      inset: 0,
      background: `linear-gradient(180deg, rgba(11,12,14,0.05) 0%, rgba(11,12,14,0.18) 35%, rgba(11,12,14,0.72) 70%, ${tokens.color.ink[900]} 100%)`,
      pointerEvents: "none" as const,
    }} />
  );
}

/** Full-width signal-red Breaking bar */
export function FlashBar({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      width: "100%",
      backgroundColor: tokens.color.accent.red,  // #C2483B
      padding: "20px 60px",
      boxSizing: "border-box" as const,
      fontSize: 30,
      fontWeight: 700,
      letterSpacing: "0.06em",
      textTransform: "uppercase" as const,
      color: "#FFFFFF",
      fontFamily: tokens.font.sans,
    }}>
      {children}
    </div>
  );
}

/** EVIDENCED meta label — green text, NO checkmark (brand spec) */
export function EvidencedBadge({ accent = tokens.color.accent.green }: AccentProps) {
  return (
    <div style={{
      fontSize: 22,
      fontWeight: 600,
      letterSpacing: "0.12em",
      textTransform: "uppercase" as const,
      color: accent,
      fontFamily: tokens.font.sans,
      marginBottom: 32,
    }}>
      EVIDENCED
    </div>
  );
}
