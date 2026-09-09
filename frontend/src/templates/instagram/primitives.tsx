/**
 * ETHIOTIMES Instagram post primitives.
 *
 * All inline styles — Playwright screenshots these components directly.
 * Never use Tailwind classes inside this file.
 */
import { tokens } from "@/lib/design-tokens";

interface AccentProps {
  accent?: string;
}

/** Category pill — outlined, uppercase, small caps */
export function Pill({ children, accent = tokens.color.accent.green }: AccentProps & { children: React.ReactNode }) {
  return (
    <span style={{
      display: "inline-block",
      border: `2px solid ${accent}`,
      color: accent,
      borderRadius: 999,
      padding: "10px 24px",
      fontSize: 26,
      fontWeight: 600,
      letterSpacing: "0.10em",
      textTransform: "uppercase" as const,
      fontFamily: tokens.font.sans,
    }}>
      {children}
    </span>
  );
}

/** Display headline */
export function Headline({ children, size = 104 }: { children: React.ReactNode; size?: number }) {
  return (
    <h1 style={{
      fontFamily: tokens.font.display,
      fontWeight: 600,
      fontSize: size,
      lineHeight: 1.02,
      letterSpacing: "-0.01em",
      margin: "28px 0 0",
      maxWidth: "94%",
      color: tokens.color.paper[50],
    }}>
      {children}
    </h1>
  );
}

/** Deck / subheadline */
export function Dek({ children }: { children: React.ReactNode }) {
  return (
    <p style={{
      fontSize: 38,
      lineHeight: 1.35,
      color: tokens.color.paper[300],
      margin: "22px 0 0",
      maxWidth: "88%",
      fontFamily: tokens.font.sans,
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

/** ETHIOTIMES wordmark */
export function Wordmark({ accent = tokens.color.accent.green }: AccentProps) {
  return (
    <div style={{
      fontFamily: tokens.font.display,
      fontWeight: 700,
      fontSize: 32,
      letterSpacing: "-0.01em",
      color: tokens.color.paper[50],
    }}>
      ETHIO
      <span style={{ color: tokens.color.paper[300] }}>TIMES</span>
      <span style={{ color: accent }}>.</span>
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

/** Ink gradient scrim over image zone */
export function Scrim() {
  return (
    <div style={{
      position: "absolute" as const,
      inset: 0,
      background: `linear-gradient(180deg, rgba(11,12,14,0.25) 0%, rgba(11,12,14,0.65) 50%, ${tokens.color.ink[900]} 100%)`,
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
