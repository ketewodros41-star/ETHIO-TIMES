import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { isEthiopic } from "./primitives";

/**
 * Headline Impact Post Theme (Phase 7 - Inspired by Habesha Diaspora / Modern News Broadcast).
 *
 * Features:
 * 1. Full-bleed dramatic editorial background photo in the upper 60%.
 * 2. Seamless deep ink-black horizon fade.
 * 3. Prestigious ET hexagonal monogram badge + stacked "ETHIOPIAN TIMES" brandmark.
 * 4. Mega-scale bold condensed uppercase headline with dual-tone punchline highlight.
 * 5. Minimalist bottom-left "↓ Read the caption" call-to-action.
 */
export function HeadlineImpactPost({
  format,
  data,
  highlightColor,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  highlightColor?: string;
}) {
  const { width, height, safeMargin } = FORMATS[format];
  const isAmharic = isEthiopic(data.headline) || isEthiopic(data.dek);

  // Dynamic Headline dual-color split:
  // White for primary context, electric highlight for the punchline / final words
  const words = (data.headline || "").trim().split(/\s+/);
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
    // For longer headlines (e.g. 9+ words), highlight the last 3 words
    whiteWords = words.slice(0, words.length - 3);
    highlightWords = words.slice(words.length - 3);
  }

  // Accent color: defaults to electric sky cyan (#52B8ED) or post accent
  const defaultHighlight =
    data.accent === "gold"
      ? "#FBBF24"
      : data.accent === "red"
      ? "#F87171"
      : data.accent === "green"
      ? "#4ADE80"
      : "#52B8ED";

  const activeHighlight = highlightColor || defaultHighlight;

  // Responsive headline typography per format
  const totalLength = (data.headline || "").length;
  let baseFontSize = 118;
  if (totalLength > 80) {
    baseFontSize = 96;
  } else if (totalLength > 60) {
    baseFontSize = 104;
  } else if (totalLength > 40) {
    baseFontSize = 112;
  }

  // Format-specific layout scaling:
  // Eliminates dead black voids in Story (1080x1920) and cramped stacking in Square (1080x1080).
  const layoutConfig = {
    portrait: {
      headlineSize: baseFontSize,
      photoHeight: "72%",
      photoPosition: "center 18%",
      scrim:
        "linear-gradient(180deg, rgba(7,8,10,0.02) 0%, rgba(7,8,10,0.18) 28%, rgba(7,8,10,0.65) 50%, rgba(7,8,10,0.92) 62%, #07080A 72%, #07080A 100%)",
      padding: "54px 64px 48px 64px",
      contentGap: 26,
      emblemSize: 58,
      brandFontSize: 27,
      footerPaddingTop: 16,
      arrowWidth: 22,
      arrowHeight: 40,
    },
    story: {
      headlineSize: Math.round(baseFontSize * 1.04), // 100px - 132px
      photoHeight: "88%", // Deep photo bleed behind text
      photoPosition: "center 18%",
      scrim:
        "linear-gradient(180deg, rgba(7,8,10,0.02) 0%, rgba(7,8,10,0.14) 24%, rgba(7,8,10,0.50) 48%, rgba(7,8,10,0.82) 58%, rgba(7,8,10,0.95) 68%, #07080A 82%, #07080A 100%)",
      padding: "100px 72px 90px 72px",
      contentGap: 32,
      emblemSize: 66,
      brandFontSize: 30,
      footerPaddingTop: 22,
      arrowWidth: 24,
      arrowHeight: 44,
    },
    square: {
      headlineSize: Math.round(baseFontSize * 0.84), // 84px - 108px
      photoHeight: "78%",
      photoPosition: "center 14%",
      scrim:
        "linear-gradient(180deg, rgba(7,8,10,0.02) 0%, rgba(7,8,10,0.20) 24%, rgba(7,8,10,0.68) 46%, rgba(7,8,10,0.94) 58%, #07080A 70%, #07080A 100%)",
      padding: "44px 56px 40px 56px",
      contentGap: 20,
      emblemSize: 52,
      brandFontSize: 24,
      footerPaddingTop: 14,
      arrowWidth: 20,
      arrowHeight: 36,
    },
  }[format];

  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        overflow: "hidden",
        backgroundColor: "#07080A",
        color: "#FFFFFF",
        fontFamily: tokens.font.sans,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        padding: layoutConfig.padding,
        boxSizing: "border-box",
      }}
    >
      {/* Upper Photo Zone with Natural Editorial Depth */}
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
              height: layoutConfig.photoHeight,
              objectFit: "cover",
              objectPosition: layoutConfig.photoPosition,
              imageRendering: "auto",
              WebkitBackfaceVisibility: "hidden",
            }}
          />

          {/* Deep Cinematic Horizon Scrim */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: layoutConfig.scrim,
              pointerEvents: "none",
            }}
          />
        </>
      )}

      {/* Main Content Overlay */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          gap: layoutConfig.contentGap,
          marginBottom: 16,
        }}
      >
        {/* Brand Header: ET Hexagon Badge + ETHIOPIAN TIMES */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          {/* ET Hexagonal Monogram */}
          <svg
            width={layoutConfig.emblemSize}
            height={layoutConfig.emblemSize}
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
            <circle cx="77" cy="68" r="3.2" fill={activeHighlight} />
          </svg>

          {/* Stacked Wordmark */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              lineHeight: 0.92,
              textAlign: "left",
              fontFamily: tokens.font.poster,
            }}
          >
            <span
              style={{
                fontSize: layoutConfig.brandFontSize,
                fontWeight: 900,
                letterSpacing: "0.05em",
                color: "#FFFFFF",
              }}
            >
              ETHIOPIAN
            </span>
            <span
              style={{
                fontSize: layoutConfig.brandFontSize,
                fontWeight: 900,
                letterSpacing: "0.05em",
                color: "#FFFFFF",
              }}
            >
              TIMES
            </span>
          </div>
        </div>

        {/* Mega Impact Bold Condensed Headline (Anton for Latin, Noto Sans Ethiopic 900 for Amharic) */}
        <h1
          style={{
            fontFamily: isAmharic ? tokens.font.amharicPoster : tokens.font.poster,
            fontWeight: 900,
            fontSize: isAmharic ? Math.round(layoutConfig.headlineSize * 0.94) : layoutConfig.headlineSize,
            lineHeight: isAmharic ? 1.14 : 1.02,
            letterSpacing: isAmharic ? "0em" : "-0.005em",
            textTransform: isAmharic ? "none" : "uppercase",
            margin: "2px 0 0",
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
      </div>

      {/* Footer Line: "↓ Read the caption" / "መግለጫውን ያንብቡ" Call-To-Action */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          paddingTop: layoutConfig.footerPaddingTop,
          borderTop: "1px solid rgba(255,255,255,0.08)",
          marginTop: layoutConfig.footerPaddingTop,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {/* Signal Downward Arrow */}
          <svg
            width={layoutConfig.arrowWidth}
            height={layoutConfig.arrowHeight}
            viewBox="0 0 24 28"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M12 2 V24 M4 16 L12 24 L20 16"
              stroke="#EF4444"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              lineHeight: isAmharic ? 1.25 : 1.1,
              fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
              color: tokens.color.paper[300],
            }}
          >
            <span style={{ fontSize: isAmharic ? 20 : 24, fontWeight: 600 }}>
              {isAmharic ? "መግለጫውን" : "Read the"}
            </span>
            <span style={{ fontSize: isAmharic ? 20 : 24, fontWeight: 700, color: "#FFFFFF" }}>
              {isAmharic ? "ያንብቡ" : "caption"}
            </span>
          </div>
        </div>

        {/* Source & Date Attribution */}
        <div
          style={{
            textAlign: "right",
            fontSize: 22,
            fontFamily: tokens.font.sans,
            color: tokens.color.paper[500],
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          <div>{data.source || "ETHIOPIAN TIMES"}</div>
          {data.dateLabel && (
            <div style={{ marginTop: 4, fontSize: 19, color: tokens.color.paper[500] }}>
              {data.dateLabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
