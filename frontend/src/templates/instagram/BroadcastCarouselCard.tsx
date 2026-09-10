import { tokens } from "@/lib/design-tokens";
import { FORMATS, type InstagramFormat } from "./formats";
import type { CarouselSlideData } from "./CarouselCard";

/**
 * Broadcast Impact Carousel Slide (5-Page Deck).
 *
 * Implements the Habesha broadcast aesthetic across all 5 slide types:
 * - Slide 1 (Cover): Full-bleed photo, ET monogram, Anton poster font, cyan punchline.
 * - Slide 2 (The Facts): Big condensed headline, 1 short high-impact statement.
 * - Slide 3 (Key Points): 2-3 punchy numeric bullet points with highlighted keywords.
 * - Slide 4 (Why It Matters): Short strategic impact statement.
 * - Slide 5 (Sources & CTA): Verified source tags + signature red downward arrow "Read the caption".
 */
export function BroadcastCarouselCard({
  format = "portrait",
  slide,
  category = "ETHIOPIAN TIMES",
  dateLabel,
  highlightColor = "#52B8ED",
}: {
  format?: InstagramFormat;
  slide: CarouselSlideData;
  category?: string;
  dateLabel?: string;
  highlightColor?: string;
}) {
  const { width, height } = FORMATS[format] ?? FORMATS.portrait;
  const activeHighlight = slide.highlightColor || highlightColor;

  const padSlide = (n: number) => String(n).padStart(2, "0");

  // Dynamic Headline split for cover or slide headers
  const words = (slide.header || "").trim().split(/\s+/).filter(Boolean);
  let whiteWords: string[] = [];
  let highlightWords: string[] = [];

  if (words.length <= 2) {
    whiteWords = [words[0] || ""];
    highlightWords = words.slice(1);
  } else if (words.length <= 5) {
    whiteWords = words.slice(0, words.length - 1);
    highlightWords = words.slice(words.length - 1);
  } else {
    whiteWords = words.slice(0, words.length - 2);
    highlightWords = words.slice(words.length - 2);
  }

  // Type-specific slide badges
  const slideBadges: Record<string, string> = {
    cover: "01 · BREAKING INTELLIGENCE",
    what_happened: "02 · THE FACTS",
    key_facts: "03 · VERIFIED DEVELOPMENTS",
    why_it_matters: "04 · STRATEGIC IMPACT",
    sources: "05 · NEWS DESK VERIFIED",
  };

  const badgeText = slideBadges[slide.slide_type] || `${padSlide(slide.slide_number)} · BRIEF`;

  // Dynamic slide font sizing (stays punchy and never overflows)
  const isCover = slide.slide_type === "cover";
  const headerFontSize = isCover
    ? (slide.header.length > 60 ? 104 : 118)
    : 84;

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
        padding: "54px 64px 48px 64px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      {/* Background Photo (Cover uses upper 68% bleed, subsequent slides use dark ambient glow) */}
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
              height: isCover ? "68%" : "45%",
              objectFit: "cover",
              objectPosition: "center 16%",
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
                ? "linear-gradient(180deg, rgba(7, 8, 11, 0.0) 0%, rgba(7, 8, 11, 0.0) 28%, rgba(7, 8, 11, 0.22) 40%, rgba(7, 8, 11, 0.68) 50%, rgba(7, 8, 11, 0.92) 60%, #07080B 68%, #07080B 100%)"
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
            width="52"
            height="52"
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
            <span style={{ fontSize: 24, color: "#FFFFFF", fontWeight: 900 }}>
              ETHIOPIAN
            </span>
            <span style={{ fontSize: 24, color: "#FFFFFF", fontWeight: 900 }}>
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
            fontFamily: tokens.font.poster,
            fontWeight: 900,
            fontSize: headerFontSize,
            lineHeight: 1.02,
            letterSpacing: "-0.005em",
            textTransform: "uppercase",
            margin: 0,
            padding: 0,
            maxWidth: "100%",
            wordBreak: "break-word",
          }}
        >
          <span style={{ color: "#FFFFFF" }}>{whiteWords.join(" ")} </span>
          <span style={{ color: activeHighlight }}>{highlightWords.join(" ")}</span>
        </h1>

        {/* Short Statement / Body Text (Slides 2, 4, 5) */}
        {slide.body_text && !isCover && (
          <p
            style={{
              fontFamily: tokens.font.sans,
              fontSize: 36,
              fontWeight: 600,
              lineHeight: 1.38,
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
                    fontFamily: tokens.font.sans,
                    fontSize: 30,
                    fontWeight: 600,
                    lineHeight: 1.35,
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
                fontFamily: tokens.font.sans,
                lineHeight: 1.2,
              }}
            >
              <span style={{ fontSize: 22, color: "#94A3B8", fontWeight: 500 }}>
                Read complete investigative report
              </span>
              <span style={{ fontSize: 26, color: "#FFFFFF", fontWeight: 800 }}>
                in the caption below
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
                  fontFamily: tokens.font.sans,
                  fontSize: 22,
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  color: "#FFFFFF",
                  textTransform: "uppercase",
                }}
              >
                Swipe to read
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
                  fontFamily: tokens.font.sans,
                  fontSize: 20,
                  fontWeight: 700,
                  color: "#FFFFFF",
                }}
              >
                Read caption
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  fontFamily: tokens.font.sans,
                  fontSize: 20,
                  fontWeight: 600,
                  color: "#94A3B8",
                }}
              >
                Next slide
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
