import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";

/**
 * Broadcast Impact Post Theme (Exact Replica of Habesha Diaspora Broadcast Style).
 *
 * Visual Specifications:
 * 1. Full-bleed speaker/subject photo in the upper 68% of the canvas.
 * 2. 3-stage dark horizon scrim fading smoothly into solid #07080B jet black.
 * 3. Left-aligned ET Hexagon Monogram Emblem + stacked bold condensed "ETHIOPIAN / TIMES".
 * 4. Ultra-bold condensed Anton/Impact poster typography (fontSize: ~124px, lineHeight: 0.88).
 * 5. Dual-tone color split: crisp white (#FFFFFF) setup text + electric cyan (#52B8ED) punchline.
 * 6. Bottom-left crimson downward arrow (↓) with stacked "Read the / caption" call to action.
 */
export function BroadcastImpactPost({
  format,
  data,
  highlightColor,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  highlightColor?: string;
}) {
  const { width, height } = FORMATS[format];

  // Signature electric cyan/sky blue from the reference post
  const defaultCyan = "#52B8ED";
  const activeHighlight =
    highlightColor ||
    (data.accent === "gold"
      ? "#FBBF24"
      : data.accent === "red"
      ? "#F87171"
      : data.accent === "green"
      ? "#4ADE80"
      : defaultCyan);

  // Dynamic word splitting into white setup + highlighted punchline
  const words = (data.headline || "").trim().split(/\s+/).filter(Boolean);
  let whiteWords: string[] = [];
  let highlightWords: string[] = [];

  if (words.length <= 2) {
    whiteWords = [words[0] || ""];
    highlightWords = words.slice(1);
  } else if (words.length <= 4) {
    whiteWords = words.slice(0, words.length - 1);
    highlightWords = words.slice(words.length - 1);
  } else if (words.length <= 8) {
    whiteWords = words.slice(0, words.length - 2);
    highlightWords = words.slice(words.length - 2);
  } else {
    // For longer headlines (e.g. 9+ words), highlight the punchline (last 2 or 3 words)
    whiteWords = words.slice(0, words.length - 3);
    highlightWords = words.slice(words.length - 3);
  }

  // Responsive headline font sizing based on length
  const totalLength = (data.headline || "").length;
  let baseFontSize = 120;
  if (totalLength > 80) {
    baseFontSize = 96;
  } else if (totalLength > 60) {
    baseFontSize = 104;
  } else if (totalLength > 40) {
    baseFontSize = 112;
  } else if (totalLength < 25) {
    baseFontSize = 128;
  }

  // Format scaling
  const headlineSize =
    format === "square"
      ? Math.round(baseFontSize * 0.82)
      : format === "story"
      ? Math.round(baseFontSize * 0.94)
      : baseFontSize;

  const photoHeightPercent = format === "story" ? "74%" : format === "square" ? "62%" : "68%";

  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        overflow: "hidden",
        backgroundColor: "#07080B",
        color: "#FFFFFF",
        boxSizing: "border-box",
        padding: "54px 64px 48px 64px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {/* 1. Full-Bleed Background Photo Layer */}
      {data.imageUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={data.imageUrl}
            alt=""
            decoding="async"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: photoHeightPercent,
              objectFit: "cover",
              objectPosition: "center 16%",
              imageRendering: "auto",
              WebkitBackfaceVisibility: "hidden",
            }}
          />

          {/* 2. 3-Stage Horizon Scrim Gradient */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(180deg, rgba(7, 8, 11, 0.0) 0%, rgba(7, 8, 11, 0.0) 28%, rgba(7, 8, 11, 0.22) 40%, rgba(7, 8, 11, 0.68) 50%, rgba(7, 8, 11, 0.92) 60%, #07080B 68%, #07080B 100%)",
              pointerEvents: "none",
            }}
          />
        </>
      )}

      {/* 3. Main Foreground Content Layer */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          gap: 26,
        }}
      >
        {/* Brand Header: ET Hexagon Emblem + Stacked ETHIOPIAN TIMES */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          {/* Geometric ET Monogram Shield */}
          <svg
            width="60"
            height="60"
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ flexShrink: 0 }}
          >
            <polygon
              points="50,6 88,28 88,72 50,94 12,72 12,28"
              stroke="#FFFFFF"
              strokeWidth="7"
              strokeLinejoin="round"
              fill="none"
            />
            {/* Monogram E */}
            <path
              d="M32 30 H49 M32 50 H45 M32 70 H49 M32 30 V70"
              stroke="#FFFFFF"
              strokeWidth="6.5"
              strokeLinecap="square"
              strokeLinejoin="miter"
            />
            {/* Monogram T */}
            <path
              d="M52 30 H80 M66 30 V70"
              stroke="#FFFFFF"
              strokeWidth="6.5"
              strokeLinecap="square"
              strokeLinejoin="miter"
            />
            <circle cx="79" cy="70" r="3.2" fill={activeHighlight} />
          </svg>

          {/* Stacked Wordmark in Matching Heavy Condensed Font */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontFamily: tokens.font.poster,
              lineHeight: 0.92,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            <span
              style={{
                fontSize: 27,
                color: "#FFFFFF",
                fontWeight: 900,
              }}
            >
              ETHIOPIAN
            </span>
            <span
              style={{
                fontSize: 27,
                color: "#FFFFFF",
                fontWeight: 900,
              }}
            >
              TIMES
            </span>
          </div>
        </div>

        {/* 4. Ultra-Bold Condensed Anton/Impact Headline */}
        <h1
          style={{
            fontFamily: tokens.font.poster,
            fontWeight: 900,
            fontSize: headlineSize,
            lineHeight: 1.02,
            letterSpacing: "-0.005em",
            textTransform: "uppercase",
            margin: "2px 0 0",
            padding: 0,
            maxWidth: "100%",
            wordBreak: "break-word",
          }}
        >
          <span style={{ color: "#FFFFFF" }}>
            {whiteWords.join(" ")}{" "}
          </span>
          <span style={{ color: activeHighlight }}>
            {highlightWords.join(" ")}
          </span>
        </h1>

        {/* 5. Footer: Crimson Downward Arrow + "Read the caption" */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 16,
          }}
        >
          {/* Signal Downward Arrow & CTA */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <svg
              width="22"
              height="40"
              viewBox="0 0 24 38"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 2 V34 M4 26 L12 34 L20 26"
                stroke="#EF4444"
                strokeWidth="3.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                fontFamily: tokens.font.sans,
                lineHeight: 1.15,
              }}
            >
              <span style={{ fontSize: 22, color: "#94A3B8", fontWeight: 500 }}>
                Read the
              </span>
              <span style={{ fontSize: 22, color: "#FFFFFF", fontWeight: 700 }}>
                caption
              </span>
            </div>
          </div>

          {/* Minimal Attribution / Date */}
          {data.source && (
            <div
              style={{
                textAlign: "right",
                fontSize: 18,
                fontFamily: tokens.font.sans,
                color: "#64748B",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                fontWeight: 500,
              }}
            >
              <div>{data.source}</div>
              {data.dateLabel && (
                <div style={{ marginTop: 2, fontSize: 16, color: "#475569" }}>
                  {data.dateLabel}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
