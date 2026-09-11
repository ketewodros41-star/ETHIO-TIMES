import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Dek, Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function PoliticsSensitivePost({
  format,
  data,
  sourceCount,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  sourceCount?: number;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.gold;
  const headlineSizes = { portrait: 96, square: 80, story: 84 };
  const headlineSize = headlineSizes[format] ?? 88;

  const countLabel = sourceCount ? `${sourceCount} INDEPENDENT SOURCES CONFIRMED` : "MULTI-SOURCE VERIFICATION";

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
        boxSizing: "border-box",
      }}
    >
      {/* Top Advisory Banner */}
      <div
        style={{
          width: "100%",
          backgroundColor: tokens.color.ink[800],
          borderBottom: `2px solid ${accent}`,
          padding: "16px 40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxSizing: "border-box",
          zIndex: 2,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 20,
            fontWeight: 700,
            letterSpacing: "0.15em",
            color: accent,
            textTransform: "uppercase",
          }}
        >
          VERIFIED REPORTING · DEVELOPING DEVELOPMENTS
        </span>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 18,
            letterSpacing: "0.1em",
            color: tokens.color.paper[300],
          }}
        >
          {countLabel}
        </span>
      </div>

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
              opacity: 0.3,
            }}
          />
          <Scrim />
        </>
      )}

      {/* Main Content Area */}
      <div style={{ position: "relative", zIndex: 1, padding: safeMargin, paddingTop: 32 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Pill accent={accent}>{data.category || "POLITICS"}</Pill>
        </div>

        <Headline size={headlineSize}>{data.headline}</Headline>
        {data.dek && <Dek>{data.dek}</Dek>}

        <Rule accent={accent} />

        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <Footer source={data.source} date={data.dateLabel} accent={accent} />
          <Wordmark accent={accent} />
        </div>
      </div>
    </div>
  );
}
