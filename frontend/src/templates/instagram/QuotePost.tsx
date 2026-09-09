import { tokens } from "@/lib/design-tokens";
import type { PostTemplateData } from "./PostTemplate";
import { FORMATS, type InstagramFormat } from "./formats";
import { Footer, Pill, Rule, Scrim, Wordmark } from "./primitives";

export function QuotePost({
  format,
  data,
  speaker,
  speakerRole,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
  speaker?: string;
  speakerRole?: string;
}) {
  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accent = tokens.color.accent.green;

  const quoteText = data.dek || data.headline;
  const speakerName = speaker || data.source || "Official Source";

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

      {/* Header */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <Pill accent={accent}>{data.category || "QUOTATION"}</Pill>
      </div>

      {/* Quote Body */}
      <div style={{ position: "relative", zIndex: 1, padding: "20px 0" }}>
        {/* Large Decorative Quote Glyph */}
        <div
          style={{
            fontFamily: tokens.font.display,
            fontSize: 140,
            lineHeight: 0.8,
            color: accent,
            marginBottom: -20,
            opacity: 0.9,
          }}
        >
          “
        </div>

        <blockquote
          style={{
            fontFamily: tokens.font.display,
            fontSize: 64,
            fontWeight: 600,
            lineHeight: 1.15,
            letterSpacing: "-0.01em",
            color: tokens.color.paper[50],
            margin: "0 0 32px 0",
            maxWidth: "96%",
          }}
        >
          {quoteText}
        </blockquote>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 40, height: 3, backgroundColor: accent }} />
          <div>
            <div
              style={{
                fontFamily: tokens.font.sans,
                fontSize: 32,
                fontWeight: 700,
                color: tokens.color.paper[50],
              }}
            >
              {speakerName}
            </div>
            {speakerRole && (
              <div
                style={{
                  fontFamily: tokens.font.mono,
                  fontSize: 22,
                  color: tokens.color.paper[300],
                  letterSpacing: "0.08em",
                }}
              >
                {speakerRole}
              </div>
            )}
          </div>
        </div>
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
