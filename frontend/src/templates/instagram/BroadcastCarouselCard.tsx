import { tokens } from "@/lib/design-tokens";
import { FORMATS, type InstagramFormat } from "./formats";
import type { CarouselSlideData } from "./CarouselCard";
import { isEthiopic } from "./primitives";
import { parseHeadlineSegments, type HighlightMode, type HeadlineSegment } from "./headline-highlighter";

/**
 * Broadcast Impact Carousel Slide (5-Page Deck).
 *
 * Implements the Habesha broadcast aesthetic across all 5 slide types:
 * - Slide 1 (Cover): Full-bleed photo, ET monogram, Anton poster font (or Noto Sans Ethiopic 900), cyan punchline.
 * - Slide 2 (The Facts): Big condensed headline, 1 short high-impact statement.
 * - Slide 3 (Key Points): 2-3 punchy numeric bullet points with highlighted keywords.
 * - Slide 4 (Why It Matters): Short strategic impact statement.
 * - Slide 5 (Sources & CTA): Verified source tags + signature red downward arrow "Read the caption" ("መግለጫውን ያንብቡ").
 */
export function BroadcastCarouselCard({
  format = "portrait",
  slide,
  category,
  dateLabel,
  highlightColor = "#00F0FF",
}: {
  format?: InstagramFormat;
  slide: CarouselSlideData;
  category?: string;
  dateLabel?: string;
  highlightColor?: string;
}) {
  const { width, height } = FORMATS[format] ?? FORMATS.portrait;
  const activeHighlight = slide.highlightColor || highlightColor;

  const isAmharic =
    isEthiopic(slide.header) ||
    isEthiopic(slide.body_text) ||
    Boolean(slide.bullet_points && slide.bullet_points.some((p) => isEthiopic(p)));

  const padSlide = (n: number) => String(n).padStart(2, "0");

  // Multi-position headline segmentation
  const { segments } = parseHeadlineSegments(slide.header, {
    mode: (slide as any).highlightMode || "auto",
    customIndices: (slide as any).highlightIndices,
  });

  // Type-specific slide badges
  const slideBadges: Record<string, string> = {
    cover: "01 · BREAKING INTELLIGENCE",
    what_happened: "02 · THE FACTS",
    key_facts: "03 · VERIFIED DEVELOPMENTS",
    why_it_matters: "04 · STRATEGIC IMPACT",
    sources: "05 · NEWS DESK VERIFIED",
  };

  const amharicSlideBadges: Record<string, string> = {
    cover: "01 · ሰበር መረጃ",
    what_happened: "02 · ዋና ዋና ነጥቦች",
    key_facts: "03 · የተረጋገጡ ዝርዝሮች",
    why_it_matters: "04 · ለምን አሳሳቢ ሆነ?",
    sources: "05 · የተረጋገጠ መረጃ",
  };

  const badgeText = isAmharic
    ? amharicSlideBadges[slide.slide_type] || `${padSlide(slide.slide_number)} · አጭር መግለጫ`
    : slideBadges[slide.slide_type] || `${padSlide(slide.slide_number)} · BRIEF`;

  // Dynamic slide font sizing (stays punchy and never overflows)
  const isCover = slide.slide_type === "cover";
  const baseHeaderFontSize = isCover
    ? (slide.header.length > 60 ? 104 : 118)
    : 84;

  const layoutConfig = {
    portrait: {
      padding: "54px 64px 48px 64px",
      coverPhotoHeight: "72%",
      photoPosition: "center 16%",
      coverScrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.0) 0%, rgba(7, 8, 11, 0.0) 26%, rgba(7, 8, 11, 0.20) 38%, rgba(7, 8, 11, 0.65) 50%, rgba(7, 8, 11, 0.92) 62%, #07080B 72%, #07080B 100%)",
      headerFontSize: baseHeaderFontSize,
      emblemSize: 52,
      brandFontSize: 24,
    },
    story: {
      padding: "100px 72px 90px 72px",
      coverPhotoHeight: "88%",
      photoPosition: "center 18%",
      coverScrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.0) 0%, rgba(7, 8, 11, 0.0) 24%, rgba(7, 8, 11, 0.15) 36%, rgba(7, 8, 11, 0.52) 48%, rgba(7, 8, 11, 0.82) 58%, rgba(7, 8, 11, 0.95) 68%, #07080B 82%, #07080B 100%)",
      headerFontSize: Math.round(baseHeaderFontSize * 1.05),
      emblemSize: 60,
      brandFontSize: 28,
    },
    square: {
      padding: "44px 56px 40px 56px",
      coverPhotoHeight: "78%",
      photoPosition: "center 14%",
      coverScrim:
        "linear-gradient(180deg, rgba(7, 8, 11, 0.0) 0%, rgba(7, 8, 11, 0.0) 18%, rgba(7, 8, 11, 0.25) 32%, rgba(7, 8, 11, 0.70) 45%, rgba(7, 8, 11, 0.94) 58%, #07080B 70%, #07080B 100%)",
      headerFontSize: Math.round(baseHeaderFontSize * 0.85),
      emblemSize: 46,
      brandFontSize: 21,
    },
  }[format];

  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        overflow: "hidden",
        backgroundColor: "#07080B",
        color: "#FFFFFF",
        boxSizing: "border-box",
        padding: layoutConfig.padding,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      {/* Background Photo (Cover uses deep bleed, subsequent slides use dark ambient glow) */}
      {slide.imageUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={slide.imageUrl}
            alt=""
            decoding="async"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: isCover ? layoutConfig.coverPhotoHeight : "45%",
              objectFit: "cover",
              objectPosition: isCover ? layoutConfig.photoPosition : "center 16%",
              opacity: isCover ? 1 : 0.22,
              filter: isCover ? "none" : "grayscale(30%) blur(2px)",
              WebkitBackfaceVisibility: "hidden",
            }}
          />
          {/* Scrim Gradient */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: isCover
                ? layoutConfig.coverScrim
                : "linear-gradient(180deg, rgba(7, 8, 11, 0.5) 0%, rgba(7, 8, 11, 0.85) 35%, #07080B 55%, #07080B 100%)",
              pointerEvents: "none",
            }}
          />
        </>
      )}

      {/* Top Header: ET Hexagon Monogram + Stacked Wordmark + Slide Index */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Brand Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <svg
            width={layoutConfig.emblemSize}
            height={layoutConfig.emblemSize}
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ flexShrink: 0 }}
          >
            <polygon
              points="50,6 88,28 88,72 50,94 12,72 12,28"
              stroke="#FFFFFF"
              strokeWidth="7"
              strokeLinejoin="round"
              fill="none"
            />
            <path
              d="M32 30 H49 M32 50 H45 M32 70 H49 M32 30 V70"
              stroke="#FFFFFF"
              strokeWidth="6.5"
              strokeLinecap="square"
            />
            <path
              d="M52 30 H80 M66 30 V70"
              stroke="#FFFFFF"
              strokeWidth="6.5"
              strokeLinecap="square"
            />
            <circle cx="79" cy="70" r="3.2" fill={activeHighlight} />
          </svg>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontFamily: tokens.font.poster,
              lineHeight: 0.92,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            <span style={{ fontSize: layoutConfig.brandFontSize, color: "#FFFFFF", fontWeight: 900 }}>
              ETHIOPIAN
            </span>
            <span style={{ fontSize: layoutConfig.brandFontSize, color: "#FFFFFF", fontWeight: 900 }}>
              TIMES
            </span>
          </div>
        </div>

        {/* Slide Counter Capsule */}
        <div
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 20,
            fontWeight: 800,
            letterSpacing: "0.1em",
            color: "#FFFFFF",
            backgroundColor: "rgba(255, 255, 255, 0.08)",
            padding: "6px 16px",
            borderRadius: 999,
            border: "1px solid rgba(255, 255, 255, 0.12)",
          }}
        >
          <span style={{ color: activeHighlight }}>{padSlide(slide.slide_number)}</span>
          <span style={{ color: "#64748B", margin: "0 6px" }}>/</span>
          <span style={{ color: "#94A3B8" }}>{padSlide(slide.total_slides)}</span>
        </div>
      </div>

      {/* Main Slide Content Area */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          justifyContent: isCover ? "flex-end" : "center",
          flex: 1,
          padding: isCover ? "0 0 16px 0" : "40px 0 20px 0",
          gap: 20,
        }}
      >
        {/* Topic Tag for Slides 2-5 */}
        {!isCover && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              fontFamily: tokens.font.mono,
              fontSize: 19,
              fontWeight: 800,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: activeHighlight,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: activeHighlight,
              }}
            />
            <span>{badgeText}</span>
          </div>
        )}

        {/* Header / Headline */}
        <h1
          style={{
            fontFamily: isAmharic ? tokens.font.amharicPoster : tokens.font.poster,
            fontWeight: 900,
            fontSize: isAmharic ? Math.round(layoutConfig.headerFontSize * 0.94) : layoutConfig.headerFontSize,
            lineHeight: isAmharic ? 1.14 : 1.02,
            letterSpacing: isAmharic ? "0em" : "-0.005em",
            textTransform: isAmharic ? "none" : "uppercase",
            margin: 0,
            padding: 0,
            maxWidth: "100%",
            wordBreak: "break-word",
          }}
        >
          {segments.map((seg, idx) => (
            <span
              key={idx}
              style={{
                color: seg.isHighlight ? activeHighlight : "#FFFFFF",
              }}
            >
              {seg.text}
              {idx < segments.length - 1 ? " " : ""}
            </span>
          ))}
        </h1>

        {/* Short Statement / Body Text (Slides 2, 4, 5) */}
        {slide.body_text && !isCover && (
          <p
            style={{
              fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
              fontSize: 36,
              fontWeight: 600,
              lineHeight: isAmharic ? 1.48 : 1.38,
              color: tokens.color.paper[50],
              margin: "6px 0 0 0",
              maxWidth: "96%",
            }}
          >
            {slide.body_text}
          </p>
        )}

        {/* Bullet Points (Slide 3 & 5) - Short & High Impact */}
        {slide.bullet_points && slide.bullet_points.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 8 }}>
            {slide.bullet_points.slice(0, 3).map((point, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 18,
                  backgroundColor: "rgba(255, 255, 255, 0.04)",
                  padding: "18px 22px",
                  borderRadius: 10,
                  borderLeft: `4px solid ${activeHighlight}`,
                }}
              >
                <span
                  style={{
                    fontFamily: tokens.font.mono,
                    fontSize: 24,
                    fontWeight: 900,
                    color: activeHighlight,
                    lineHeight: 1.2,
                  }}
                >
                  {padSlide(idx + 1)}
                </span>
                <span
                  style={{
                    fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                    fontSize: 30,
                    fontWeight: 600,
                    lineHeight: isAmharic ? 1.45 : 1.35,
                    color: tokens.color.paper[50],
                  }}
                >
                  {point}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Slide 5 Signature Box: Full Story in Caption */}
        {slide.slide_type === "sources" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              marginTop: 12,
              padding: "18px 24px",
              backgroundColor: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              borderRadius: 10,
            }}
          >
            <svg
              width="24"
              height="38"
              viewBox="0 0 24 38"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 2 V34 M4 26 L12 34 L20 26"
                stroke="#EF4444"
                strokeWidth="3.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                lineHeight: 1.2,
              }}
            >
              <span style={{ fontSize: 22, color: "#94A3B8", fontWeight: 500 }}>
                {isAmharic ? "ሙሉውን ዝርዝር ዘገባ" : "Read complete investigative report"}
              </span>
              <span style={{ fontSize: 26, color: "#FFFFFF", fontWeight: 800 }}>
                {isAmharic ? "ከታች ባለው መግለጫ ያንብቡ" : "in the caption below"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Footer Navigation Bar */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          paddingTop: 18,
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          marginTop: 8,
        }}
      >
        {/* Left Action Indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {isCover ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                  fontSize: 22,
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  color: "#FFFFFF",
                  textTransform: isAmharic ? "none" : "uppercase",
                }}
              >
                {isAmharic ? "ለማንበብ ወደ ግራ ይሳቡ" : "Swipe to read"}
              </span>
              <span style={{ fontSize: 24, color: activeHighlight, fontWeight: 900 }}>
                →
              </span>
            </div>
          ) : slide.slide_type === "sources" ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 22, color: "#EF4444", fontWeight: 900 }}>↓</span>
              <span
                style={{
                  fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                  fontSize: 20,
                  fontWeight: 700,
                  color: "#FFFFFF",
                }}
              >
                {isAmharic ? "መግለጫውን ያንብቡ" : "Read caption"}
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  fontFamily: isAmharic ? tokens.font.amharicSans : tokens.font.sans,
                  fontSize: 20,
                  fontWeight: 600,
                  color: "#94A3B8",
                }}
              >
                {isAmharic ? "ቀጣይ ገጽ" : "Next slide"}
              </span>
              <span style={{ fontSize: 20, color: activeHighlight }}>→</span>
            </div>
          )}
        </div>

        {/* Source / Date Label */}
        <div
          style={{
            fontFamily: tokens.font.sans,
            fontSize: 18,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "#64748B",
            textAlign: "right",
          }}
        >
          {slide.source_attribution || "ETHIOPIAN TIMES"}
          {dateLabel ? ` · ${dateLabel}` : ""}
        </div>
      </div>
    </div>
  );
}
