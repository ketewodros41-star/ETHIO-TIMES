import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Dek, EvidencedBadge, Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function VerifiedBriefPost({
  format,
  data,
  verifiedSourceCount,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  verifiedSourceCount?: number;
}) {
  const { width, height, safeMargin } = FORMATS[format];
  const accent = tokens.color.accent.green;
  const headlineSizes = { portrait: 104, square: 84, story: 90 };
  const headlineSize = headlineSizes[format] ?? 96;
  const sourceLabel = verifiedSourceCount
    ? `${verifiedSourceCount} VERIFIED SOURCE${verifiedSourceCount !== 1 ? "S" : ""}`
    : data.source;

  return (
    <div style={{
      width, height,
      position: "relative",
      overflow: "hidden",
      backgroundColor: tokens.color.ink[900],
      color: tokens.color.paper[50],
      fontFamily: tokens.font.sans,
      display: "flex",
      flexDirection: "column",
      justifyContent: "flex-end",
      padding: safeMargin,
      boxSizing: "border-box",
    }}>
      {/* Image zone + scrim */}
      {data.imageUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={data.imageUrl} alt="" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
          <Scrim />
        </>
      )}
      {/* Content */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <EvidencedBadge accent={accent} />
        <Pill accent={accent}>{data.category}</Pill>
        <Headline size={headlineSize}>{data.headline}</Headline>
        {data.dek && <Dek>{data.dek}</Dek>}
        <Rule accent={accent} />
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <Footer source={sourceLabel} date={data.dateLabel} accent={accent} />
          <Wordmark accent={accent} />
        </div>
      </div>
    </div>
  );
}
