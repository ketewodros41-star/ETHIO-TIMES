import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { FlashBar, Footer, Headline, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function BreakingPost({
  format,
  data,
  flashText,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  flashText?: string; // short_summary for FlashBar; falls back to data.dek
}) {
  const { width, height, safeMargin } = FORMATS[format];
  const accent = tokens.color.accent.red; // #C2483B
  const headlineSizes = { portrait: 116, square: 92, story: 100 };
  const headlineSize = headlineSizes[format] ?? 110;
  const barText = flashText || data.dek || "Developing story";

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
      justifyContent: "space-between",
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

      {/* FlashBar — top */}
      <div style={{ position: "relative", zIndex: 1, width: "100%" }}>
        <FlashBar>BREAKING — {barText}</FlashBar>
      </div>

      {/* Content — bottom */}
      <div style={{ position: "relative", zIndex: 1, padding: safeMargin, paddingTop: 0 }}>
        <Pill accent={accent}>{data.category}</Pill>
        <Headline size={headlineSize}>{data.headline}</Headline>
        {/* No Dek by design — headline carries full weight */}
        <Rule accent={accent} />
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <Footer source={data.source} date={data.dateLabel} accent={accent} />
          <Wordmark accent={accent} />
        </div>
      </div>
    </div>
  );
}
