/**
 * ETHIOTIMES Instagram Carousel Slide Component.
 * Strict inline styles for Playwright rendering safety.
 */
import { tokens } from "@/lib/design-tokens";
import { FORMATS, type InstagramFormat } from "./formats";
import { Footer, Pill, Rule, Scrim, Wordmark } from "./primitives";
import { BroadcastCarouselCard } from "./BroadcastCarouselCard";

export interface CarouselSlideData {
  slide_number: number;
  total_slides: number;
  slide_type: "cover" | "what_happened" | "key_facts" | "why_it_matters" | "what_next" | "sources" | string;
  header: string;
  body_text?: string | null;
  bullet_points?: string[];
  source_attribution?: string | null;
  accent?: string;
  theme?: string;
  highlightColor?: string;
  imageUrl?: string | null;
}

export function CarouselCard({
  format = "portrait",
  slide,
  category = "ETHIOPIA",
  dateLabel,
  theme,
  highlightColor,
}: {
  format?: InstagramFormat;
  slide: CarouselSlideData;
  category?: string;
  dateLabel?: string;
  theme?: string;
  highlightColor?: string;
}) {
  const activeTheme = slide.theme || theme;
  if (activeTheme === "broadcast_impact" || activeTheme === "headline_impact") {
    return (
      <BroadcastCarouselCard
        format={format}
        slide={slide}
        category={category}
        dateLabel={dateLabel}
        highlightColor={slide.highlightColor || highlightColor}
      />
    );
  }

  const { width, height, safeMargin } = FORMATS[format] ?? FORMATS.portrait;
  const accentColor =
    slide.accent === "red"
      ? tokens.color.accent.red
      : slide.accent === "gold"
      ? tokens.color.accent.gold
      : tokens.color.accent.green;

  const padSlideNum = (n: number) => String(n).padStart(2, "0");

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
      {/* Background Image (Cover only or if provided) */}
      {slide.imageUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={slide.imageUrl}
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

      {/* Top Header: Category & Slide Index */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Pill accent={accentColor}>{category}</Pill>
        </div>

        {/* Slide Counter Pill */}
        <div
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 24,
            fontWeight: 700,
            letterSpacing: "0.15em",
            color: tokens.color.paper[300],
            backgroundColor: "rgba(28, 31, 36, 0.8)",
            padding: "8px 20px",
            borderRadius: 999,
            border: `1px solid ${tokens.color.ink[700]}`,
          }}
        >
          {padSlideNum(slide.slide_number)} / {padSlideNum(slide.total_slides)}
        </div>
      </div>

      {/* Slide Body Content */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          flex: 1,
          padding: "32px 0",
        }}
      >
        {/* Slide Header */}
        <h2
          style={{
            fontFamily: tokens.font.display,
            fontSize: slide.slide_type === "cover" ? 92 : 76,
            fontWeight: 700,
            lineHeight: 1.06,
            letterSpacing: "-0.01em",
            color: tokens.color.paper[50],
            margin: "0 0 24px 0",
            maxWidth: "96%",
          }}
        >
          {slide.header}
        </h2>

        {/* Body Paragraph */}
        {slide.body_text && (
          <p
            style={{
              fontFamily: tokens.font.sans,
              fontSize: 36,
              lineHeight: 1.4,
              color: tokens.color.paper[300],
              margin: "0 0 24px 0",
              maxWidth: "92%",
            }}
          >
            {slide.body_text}
          </p>
        )}

        {/* Bullet Points */}
        {slide.bullet_points && slide.bullet_points.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 12 }}>
            {slide.bullet_points.map((point, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 16,
                  backgroundColor: "rgba(28, 31, 36, 0.5)",
                  padding: "16px 22px",
                  borderRadius: 8,
                  borderLeft: `3px solid ${accentColor}`,
                }}
              >
                <div
                  style={{
                    fontFamily: tokens.font.mono,
                    fontSize: 22,
                    fontWeight: 700,
                    color: accentColor,
                    lineHeight: 1.5,
                  }}
                >
                  {idx + 1}.
                </div>
                <p
                  style={{
                    fontFamily: tokens.font.sans,
                    fontSize: 30,
                    lineHeight: 1.35,
                    color: tokens.color.paper[50],
                    margin: 0,
                  }}
                >
                  {point}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Line */}
      <div style={{ position: "relative", zIndex: 2 }}>
        <Rule accent={accentColor} />
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <Footer
            source={slide.source_attribution || "ETHIOPIAN TIMES Intelligence"}
            date={dateLabel}
            accent={accentColor}
          />
          <Wordmark accent={accentColor} />
        </div>
      </div>
    </div>
  );
}
