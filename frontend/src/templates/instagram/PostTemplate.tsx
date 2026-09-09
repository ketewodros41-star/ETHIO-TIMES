import { tokens } from "@/lib/design-tokens";
import type { VisualStyle } from "@/lib/design-tokens";
import { FORMATS, type InstagramFormat } from "./formats";

export type PostTemplateData = {
  category: string;
  headline: string;
  dek?: string;
  source: string;
  dateLabel?: string;
  imageUrl?: string;
  accent?: "green" | "gold";
  style?: VisualStyle;
};

/**
 * Shared composition engine for ETHIOTIMES Instagram posts.
 *
 * Renders at TRUE pixel dimensions so a later Playwright pass can screenshot the
 * root element directly. On-screen previews scale this down with a CSS transform
 * (see the Post Studio page) while keeping the underlying box at 1:1.
 *
 * Layout order (per docs/brand-guidelines.md): category pill → headline → dek →
 * accent rule → source footer + ETHIOTIMES wordmark. Optional cinematic image
 * zone sits behind an ink gradient scrim for legibility.
 */
export function PostTemplate({
  format,
  data,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
}) {
  const { width, height, safeMargin } = FORMATS[format];
  const accent =
    data.accent === "gold" ? tokens.color.accent.gold : tokens.color.accent.green;

  const headlineSize = format === "story" ? 96 : format === "square" ? 84 : 104;

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
        justifyContent: "flex-end",
        padding: safeMargin,
        boxSizing: "border-box",
      }}
    >
      {/* Image zone + scrim */}
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
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(180deg, rgba(11,12,14,0.35) 0%, rgba(11,12,14,0.75) 55%, ${tokens.color.ink[900]} 100%)`,
            }}
          />
        </>
      )}

      {/* Content */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <span
          style={{
            display: "inline-block",
            border: `2px solid ${accent}`,
            color: accent,
            borderRadius: 999,
            padding: "10px 22px",
            fontSize: 28,
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {data.category}
        </span>

        <h1
          style={{
            fontFamily: tokens.font.display,
            fontWeight: 600,
            fontSize: headlineSize,
            lineHeight: 1.02,
            letterSpacing: "-0.01em",
            margin: "28px 0 0",
            maxWidth: "94%",
          }}
        >
          {data.headline}
        </h1>

        {data.dek && (
          <p
            style={{
              fontSize: 40,
              lineHeight: 1.3,
              color: tokens.color.paper[300],
              margin: "24px 0 0",
              maxWidth: "88%",
            }}
          >
            {data.dek}
          </p>
        )}

        <div
          style={{
            height: 2,
            width: 96,
            backgroundColor: accent,
            margin: "36px 0 24px",
          }}
        />

        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontSize: 28, color: tokens.color.paper[500] }}>
            <div style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Reported by {data.source}
            </div>
            {data.dateLabel && (
              <div style={{ marginTop: 6 }}>{data.dateLabel}</div>
            )}
          </div>
          <div
            style={{
              fontFamily: tokens.font.display,
              fontWeight: 700,
              fontSize: 34,
              letterSpacing: "-0.01em",
            }}
          >
            ETHIO
            <span style={{ color: tokens.color.paper[300] }}>TIMES</span>
            <span style={{ color: accent }}>.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
