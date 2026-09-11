import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { CountryFlagBadge, resolveCountryCode } from "@/components/country-flag";
import { isEthiopic } from "./primitives";
import { parseHeadlineSegments, type HighlightMode } from "./headline-highlighter";

/**
 * Country Spotlight Post Theme (Phase 7 - National / Pan-African Identity).
 *
 * Visual Specifications:
 * 1. Full-bleed speaker / subject photo in the upper canvas (64%-74%).
 * 2. 3-stage dark horizon scrim with linear falloff into solid black.
 * 3. Left-aligned ET Hexagon Monogram Emblem + stacked bold condensed "ETHIOPIAN / TIMES".
 * 4. National flag indicator chip highlighting country focus (e.g. 🇪🇹 Ethiopia, 🇰🇪 Kenya, 🇷🇼 Rwanda).
 * 5. Ultra-bold condensed Anton/Impact poster typography (fontSize: ~118px, lineHeight: 0.90).
 *    In Amharic: Noto Sans Ethiopic Weight 900 (Black) with 1.14 line-height & diacritic clearance.
 * 6. Dual-tone color split: crisp white (#FFFFFF) setup text + curated punchline highlights.
 * 7. Bottom-left crimson downward arrow (↓) with stacked "Read the / caption" (መግለጫውን / ያንብቡ) call to action.
 */
export function CountrySpotlightPost({
  format,
  data,
  highlightColor,
  highlightMode,
  highlightIndices,
  country,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  highlightColor?: string;
  highlightMode?: HighlightMode;
  highlightIndices?: number[];
  country?: string;
}) {
  const { width, height } = FORMATS[format];
  const isAmharic = isEthiopic(data.headline) || isEthiopic(data.dek);

  // Signature electric cyan / sky blue from broadcast reference
  const defaultCyan = "#00F0FF";
  const activeHighlight =
    highlightColor ||
    (data.accent === "gold"
      ? "#FFB800"
      : data.accent === "red"
      ? "#FF385C"
      : data.accent === "green"
      ? "#00F5A0"
      : defaultCyan);

  // Country resolution: prop > data.country > detected from headline/category
  const detectedCountry = country || data.country || `${data.headline || ""} ${data.category || ""}`;
  const countryCode = resolveCountryCode(detectedCountry);

  // Multi-position headline segmentation
  const effectiveMode = highlightMode || data.highlightMode || "auto";
  const effectiveIndices = highlightIndices || data.highlightIndices;

  const { segments, cleanHeadline } = parseHeadlineSegments(data.headline, {
    mode: effectiveMode,
    customIndices: effectiveIndices,
  });

  // Responsive headline font sizing based on length
  const totalLength = cleanHeadline.length;
  let baseFontSize = 118;
  if (totalLength > 80) {
    baseFontSize = 96;
  } else if (totalLength > 60) {
    baseFontSize = 104;
  } else if (totalLength > 40) {
    baseFontSize = 112;
  } else if (totalLength < 25) {
    baseFontSize = 126;
  }

  // Format-specific layout scaling
  const layoutConfig = {
    portrait: {
      headlineSize: baseFontSize,
      photoHeight: "74%",
      photoPosition: "center 16%",
      scrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.05) 0%, rgba(7, 8, 11, 0.15) 26%, rgba(7, 8, 11, 0.35) 38%, rgba(7, 8, 11, 0.70) 50%, rgba(7, 8, 11, 0.94) 62%, #07080B 72%, #07080B 100%)",
      padding: "54px 64px 48px 64px",
      contentGap: 26,
      emblemSize: 60,
      brandFontSize: 27,
      footerPaddingTop: 16,
      arrowWidth: 22,
      arrowHeight: 40,
      flagSize: 210,
      flagTop: 120,
      flagRight: 70,
      flagBorder: 8,
    },
    story: {
      headlineSize: Math.round(baseFontSize * 1.04), // 100px - 132px
      photoHeight: "88%",
      photoPosition: "center 18%",
      scrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.05) 0%, rgba(7, 8, 11, 0.12) 24%, rgba(7, 8, 11, 0.45) 48%, rgba(7, 8, 11, 0.80) 58%, rgba(7, 8, 11, 0.95) 68%, #07080B 82%, #07080B 100%)",
      padding: "100px 72px 90px 72px",
      contentGap: 32,
      emblemSize: 68,
      brandFontSize: 30,
      footerPaddingTop: 22,
      arrowWidth: 24,
      arrowHeight: 44,
      flagSize: 224,
      flagTop: 180,
      flagRight: 80,
      flagBorder: 9,
    },
    square: {
      headlineSize: Math.round(baseFontSize * 0.84), // 84px - 108px
      photoHeight: "78%",
      photoPosition: "center 14%",
      scrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.05) 0%, rgba(7, 8, 11, 0.20) 24%, rgba(7, 8, 11, 0.68) 46%, rgba(7, 8, 11, 0.94) 58%, #07080B 70%, #07080B 100%)",
      padding: "44px 56px 40px 56px",
      contentGap: 20,
      emblemSize: 52,
      brandFontSize: 24,
      footerPaddingTop: 14,
      arrowWidth: 20,
      arrowHeight: 36,
      flagSize: 170,
      flagTop: 65,
      flagRight: 50,
      flagBorder: 7,
    },
  }[format];

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
        padding: layoutConfig.padding,
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
              height: layoutConfig.photoHeight,
              objectFit: "cover",
              objectPosition: layoutConfig.photoPosition,
              imageRendering: "auto",
              WebkitBackfaceVisibility: "hidden",
            }}
          />

          {/* 2. Horizon Scrim Gradient Tailored to Aspect Ratio */}
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

      {/* 3. Circular Country Flag Badge (Floating Depth in Upper Right) */}
      <div
        style={{
          position: "absolute",
          top: layoutConfig.flagTop,
          right: layoutConfig.flagRight,
          zIndex: 15,
        }}
      >
        <CountryFlagBadge
          country={countryCode}
          size={layoutConfig.flagSize}
          borderWidth={layoutConfig.flagBorder}
        />
      </div>

      {/* 4. Main Foreground Content Layer */}
      <div
        style={{
          position: "relative",
          zIndex: 20,
          display: "flex",
          flexDirection: "column",
          gap: layoutConfig.contentGap,
        }}
      >
        {/* Brand Header: ET Hexagon Emblem + Stacked ETHIOPIAN TIMES */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: layoutConfig.contentGap > 24 ? 18 : 14,
          }}
        >
          {/* Geometric ET Monogram Shield */}
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
                fontSize: layoutConfig.brandFontSize,
                color: "#FFFFFF",
                fontWeight: 900,
              }}
            >
              ETHIOPIAN
            </span>
            <span
              style={{
                fontSize: layoutConfig.brandFontSize,
                color: "#FFFFFF",
                fontWeight: 900,
              }}
            >
              TIMES
            </span>
          </div>
        </div>

        {/* 5. Ultra-Bold Condensed Headline (Anton for Latin, Noto Sans Ethiopic 900 for Amharic) */}
        <h1
          style={{
            fontFamily: isAmharic ? tokens.font.amharicPoster : tokens.font.poster,
            fontWeight: 900,
            fontSize: isAmharic ? Math.round(layoutConfig.headlineSize * 0.94) : layoutConfig.headlineSize,
            lineHeight: isAmharic ? 1.14 : 1.02,
            letterSpacing: isAmharic ? "0em" : "-0.005em",
            textTransform: isAmharic ? "none" : "uppercase",
            margin: "2px 0 0",
            padding: 0,
            maxWidth: "100%",
            wordBreak: "break-word",
          }}
        >
          {segments.map((seg, idx) => (
            <span
              key={idx}
              style={{
                color: seg.isHighlight ? activeHighlight : "#FFFFFF",
              }}
            >
              {seg.text}
              {idx < segments.length - 1 ? " " : ""}
            </span>
          ))}
        </h1>

        {/* 6. Footer: Crimson Downward Arrow + "Read the caption" / "መግለጫውን ያንብቡ" */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: layoutConfig.footerPaddingTop,
            paddingTop: layoutConfig.footerPaddingTop,
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          }}
        >
          {/* Signal Downward Arrow & CTA */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <svg
              width={layoutConfig.arrowWidth}
              height={layoutConfig.arrowHeight}
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
                fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                lineHeight: isAmharic ? 1.25 : 1.15,
              }}
            >
              <span style={{ fontSize: isAmharic ? 20 : 22, color: "#94A3B8", fontWeight: 500 }}>
                {isAmharic ? "መግለጫውን" : "Read the"}
              </span>
              <span style={{ fontSize: isAmharic ? 20 : 22, color: "#FFFFFF", fontWeight: 700 }}>
                {isAmharic ? "ያንብቡ" : "caption"}
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
