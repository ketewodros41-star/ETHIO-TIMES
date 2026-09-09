import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function OfficialStatementPost({
  format,
  data,
  officialBody,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  officialBody?: string;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.gold;
  const headlineSizes = { portrait: 88, square: 74, story: 78 };
  const headlineSize = headlineSizes[format] ?? 82;

  const entity = officialBody || data.source || "OFFICIAL COMMUNIQUÉ";

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
              opacity: 0.2,
            }}
          />
          <Scrim />
        </>
      )}

      {/* Official Header Badge */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Pill accent={accent}>GOVERNMENT STATEMENT</Pill>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: "0.15em",
              color: tokens.color.paper[300],
              textTransform: "uppercase",
            }}
          >
            {entity}
          </span>
        </div>
      </div>

      {/* Main Statement Box */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          backgroundColor: "rgba(28, 31, 36, 0.7)",
          border: `1px solid ${tokens.color.ink[600]}`,
          borderTop: `4px solid ${accent}`,
          padding: "40px",
          borderRadius: 8,
          margin: "24px 0",
        }}
      >
        <Headline size={headlineSize}>{data.headline}</Headline>

        {data.dek && (
          <blockquote
            style={{
              fontFamily: tokens.font.display,
              fontSize: 36,
              fontStyle: "italic",
              lineHeight: 1.35,
              color: tokens.color.paper[50],
              margin: "24px 0 0",
              borderLeft: `3px solid ${accent}`,
              paddingLeft: 24,
            }}
          >
            “{data.dek}”
          </blockquote>
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
