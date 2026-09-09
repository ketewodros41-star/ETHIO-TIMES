import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function DataChartPost({
  format,
  data,
  statValue,
  statLabel,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  statValue?: string;
  statLabel?: string;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.gold;
  const headlineSizes = { portrait: 96, square: 80, story: 84 };
  const headlineSize = headlineSizes[format] ?? 90;

  // Extract a stat value if not provided (e.g. percent or numbers in headline)
  const displayStat = statValue || data.headline.match(/(\d+[\d.,]*%?|\$\d+[\d.,]*\w*)/)?.[0] || "INDEX";
  const displayLabel = statLabel || data.category || "Economic Indicator";

  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        overflow: "hidden",
        backgroundColor: tokens.color.ink[900],
        color: tokens.color.paper[50],
        fontFamily: tokens.font.sans,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: safeMargin,
        boxSizing: "border-box",
      }}
    >
      {data.imageUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={data.imageUrl}
            alt=""
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: 0.25,
            }}
          />
          <Scrim />
        </>
      )}

      {/* Top Bar */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Pill accent={accent}>DATA & INTEL</Pill>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: 22,
              letterSpacing: "0.1em",
              color: accent,
              textTransform: "uppercase",
            }}
          >
            {data.category}
          </span>
        </div>
        <Headline size={headlineSize}>{data.headline}</Headline>
      </div>

      {/* Center Metric Callout Box */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          backgroundColor: "rgba(28, 31, 36, 0.8)",
          borderRadius: 16,
          padding: "36px 44px",
          border: `1px solid ${tokens.color.ink[600]}`,
          borderLeft: `6px solid ${accent}`,
          margin: "24px 0",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <div>
            <div
              style={{
                fontFamily: tokens.font.mono,
                fontSize: 22,
                color: tokens.color.paper[500],
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              {displayLabel}
            </div>
            <div
              style={{
                fontFamily: tokens.font.display,
                fontSize: 88,
                fontWeight: 800,
                color: accent,
                lineHeight: 1,
                letterSpacing: "-0.02em",
              }}
            >
              {displayStat}
            </div>
          </div>
          <div
            style={{
              fontFamily: tokens.font.mono,
              fontSize: 20,
              color: tokens.color.paper[300],
              textAlign: "right",
              maxWidth: 320,
            }}
          >
            ETHIOTIMES INTELLIGENCE UNIT
          </div>
        </div>

        {data.dek && (
          <p
            style={{
              fontSize: 34,
              lineHeight: 1.35,
              color: tokens.color.paper[300],
              marginTop: 24,
              borderTop: `1px solid ${tokens.color.ink[700]}`,
              paddingTop: 16,
              marginBottom: 0,
            }}
          >
            {data.dek}
          </p>
        )}
      </div>

      {/* Footer */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <Rule accent={accent} />
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <Footer source={data.source} date={data.dateLabel} accent={accent} />
          <Wordmark accent={accent} />
        </div>
      </div>
    </div>
  );
}
