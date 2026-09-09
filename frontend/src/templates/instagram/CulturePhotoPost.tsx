import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Dek, Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function CulturePhotoPost({
  format,
  data,
  location,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  location?: string;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.gold;
  const headlineSizes = { portrait: 96, square: 80, story: 86 };
  const headlineSize = headlineSizes[format] ?? 88;

  const locLabel = location || "ETHIOPIA · ARTS & CULTURE";

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
      {/* Full-bleed Photo Background */}
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
            }}
          />
          <Scrim />
        </>
      )}

      {/* Top Locator Bar */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Pill accent={accent}>{data.category || "CULTURE"}</Pill>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: "0.15em",
              color: tokens.color.paper[50],
              textTransform: "uppercase",
            }}
          >
            {locLabel}
          </span>
        </div>
      </div>

      {/* Bottom Editorial Caption */}
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
