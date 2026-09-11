import { tokens } from "@/lib/design-tokens";
import type { VisualStyle } from "@/lib/design-tokens";
import { FORMATS, type InstagramFormat } from "./formats";

import type { ThemeId } from "./themes";
import type { HighlightMode } from "./headline-highlighter";

export type PostTemplateData = {
  category: string;
  headline: string;
  dek?: string;
  source: string;
  dateLabel?: string;
  imageUrl?: string;
  accent?: "green" | "gold" | "red";
  style?: VisualStyle;
  theme?: ThemeId;
  highlightColor?: string;
  highlightMode?: HighlightMode;
  highlightIndices?: number[];
  country?: string;
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
import { VerifiedBriefPost } from "./VerifiedBriefPost";
import { BroadcastImpactPost } from "./BroadcastImpactPost";
import { CountrySpotlightPost } from "./CountrySpotlightPost";
import { HeadlineImpactPost } from "./HeadlineImpactPost";
import { BreakingPost } from "./BreakingPost";
import { PoliticsSensitivePost } from "./PoliticsSensitivePost";
import { EconomyPost } from "./EconomyPost";
import { DataChartPost } from "./DataChartPost";
import { OfficialStatementPost } from "./OfficialStatementPost";
import { QuotePost } from "./QuotePost";
import { CulturePhotoPost } from "./CulturePhotoPost";

export function PostTemplate({
  format,
  data,
}: {
  format: InstagramFormat;
  data: PostTemplateData;
}) {
  if (data.theme) {
    switch (data.theme) {
      case "broadcast_impact": return <BroadcastImpactPost format={format} data={data} highlightColor={data.highlightColor} highlightMode={data.highlightMode} highlightIndices={data.highlightIndices} />;
      case "country_spotlight": return <CountrySpotlightPost format={format} data={data} highlightColor={data.highlightColor} highlightMode={data.highlightMode} highlightIndices={data.highlightIndices} country={data.country} />;
      case "headline_impact": return <HeadlineImpactPost format={format} data={data} highlightColor={data.highlightColor} highlightMode={data.highlightMode} highlightIndices={data.highlightIndices} />;
      case "verified_brief": return <VerifiedBriefPost format={format} data={data} />;
      case "breaking": return <BreakingPost format={format} data={data} flashText={data.dek} />;
      case "politics_sensitive": return <PoliticsSensitivePost format={format} data={data} />;
      case "economy": return <EconomyPost format={format} data={data} />;
      case "data_chart": return <DataChartPost format={format} data={data} />;
      case "official_statement": return <OfficialStatementPost format={format} data={data} />;
      case "quote": return <QuotePost format={format} data={data} />;
      case "culture_photo": return <CulturePhotoPost format={format} data={data} />;
    }
  }

  const { width, height, safeMargin } = FORMATS[format];
  const accent =
    data.accent === "gold" ? tokens.color.accent.gold : data.accent === "red" ? tokens.color.accent.red : tokens.color.accent.green;

  const headlineSize = format === "story" ? 116 : format === "square" ? 88 : 104;
  const padding = format === "story" ? "100px 72px 90px 72px" : safeMargin;

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
        padding,
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
            decoding="async"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              imageRendering: "auto",
              WebkitBackfaceVisibility: "hidden",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(180deg, rgba(11,12,14,0.05) 0%, rgba(11,12,14,0.18) 35%, rgba(11,12,14,0.72) 70%, ${tokens.color.ink[900]} 100%)`,
              pointerEvents: "none",
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
