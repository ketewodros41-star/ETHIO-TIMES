import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Dek, Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function EconomyPost({
  format,
  data,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.gold;
  const headlineSizes = { portrait: 100, square: 82, story: 88 };
  const headlineSize = headlineSizes[format] ?? 92;

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
              opacity: 0.35,
            }}
          />
          <Scrim />
        </>
      )}

      {/* Top Header */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Pill accent={accent}>ECONOMY & MARKETS</Pill>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: 22,
              letterSpacing: "0.12em",
              color: tokens.color.paper[300],
            }}
          >
            FINANCIAL INTELLIGENCE
          </span>
        </div>
      </div>

      {/* Core Editorial Narrative */}
      <div style={{ position: "relative", zIndex: 1 }}>
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
