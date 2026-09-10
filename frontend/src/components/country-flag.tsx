import React from "react";

export interface CountryFlagProps {
  country?: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
  borderWidth?: number;
}

/**
 * Normalizes country names, locations, and codes to standard ISO code.
 */
export function resolveCountryCode(input?: string): string {
  if (!input) return "ET";
  const norm = input.trim().toLowerCase();

  // Direct matches
  if (norm === "et" || norm.includes("ethiop") || norm.includes("addis") || norm.includes("amhara") || norm.includes("oromia") || norm.includes("tigray") || norm.includes("abiy")) return "ET";
  if (norm === "sd" || norm.includes("sudan") || norm.includes("khartoum") || norm.includes("darfur") || norm.includes("tawila") || norm.includes("burhan") || norm.includes("hemedti")) return "SD";
  if (norm === "so" || norm.includes("somali") || norm.includes("mogadishu") || norm.includes("hargeisa")) return "SO";
  if (norm === "ke" || norm.includes("kenya") || norm.includes("nairobi") || norm.includes("ruto")) return "KE";
  if (norm === "er" || norm.includes("eritrea") || norm.includes("asmara") || norm.includes("afwerki")) return "ER";
  if (norm === "dj" || norm.includes("djibouti")) return "DJ";
  if (norm === "eg" || norm.includes("egypt") || norm.includes("cairo") || norm.includes("nile")) return "EG";
  if (norm === "ss" || norm.includes("south sudan") || norm.includes("juba")) return "SS";
  if (norm === "us" || norm === "usa" || norm.includes("united states") || norm.includes("america") || norm.includes("washington") || norm.includes("biden") || norm.includes("trump")) return "US";
  if (norm === "gb" || norm === "uk" || norm.includes("united kingdom") || norm.includes("britain") || norm.includes("london")) return "GB";
  if (norm === "ae" || norm.includes("emirates") || norm.includes("dubai") || norm.includes("uae") || norm.includes("abu dhabi")) return "AE";
  if (norm === "sa" || norm.includes("saudi") || norm.includes("riyadh")) return "SA";
  if (norm === "cn" || norm.includes("china") || norm.includes("beijing")) return "CN";
  if (norm === "tr" || norm.includes("turkey") || norm.includes("ankara") || norm.includes("erdogan")) return "TR";
  if (norm === "il" || norm.includes("israel") || norm.includes("jerusalem")) return "IL";
  if (norm === "au" || norm.includes("african union")) return "AU";

  if (input.length === 2) return input.toUpperCase();
  return "ET";
}

export const POPULAR_COUNTRIES: { code: string; label: string; flag: string }[] = [
  { code: "ET", label: "Ethiopia", flag: "🇪🇹" },
  { code: "SD", label: "Sudan", flag: "🇸🇩" },
  { code: "SO", label: "Somalia", flag: "🇸🇴" },
  { code: "KE", label: "Kenya", flag: "🇰🇪" },
  { code: "ER", label: "Eritrea", flag: "🇪🇷" },
  { code: "DJ", label: "Djibouti", flag: "🇩🇯" },
  { code: "EG", label: "Egypt", flag: "🇪🇬" },
  { code: "SS", label: "South Sudan", flag: "🇸🇸" },
  { code: "US", label: "United States", flag: "🇺🇸" },
  { code: "GB", label: "United Kingdom", flag: "🇬🇧" },
  { code: "AE", label: "UAE", flag: "🇦🇪" },
  { code: "SA", label: "Saudi Arabia", flag: "🇸🇦" },
  { code: "CN", label: "China", flag: "🇨🇳" },
];

/**
 * Pure SVG flag definitions for key nations (rendering in infinite 4K resolution).
 */
function renderFlagSvg(code: string): React.ReactNode {
  switch (code) {
    case "ET": // Ethiopia
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="none">
          <rect y="0" width="100" height="33.33" fill="#078930" />
          <rect y="33.33" width="100" height="33.34" fill="#FCD116" />
          <rect y="66.67" width="100" height="33.33" fill="#E4002B" />
          <circle cx="50" cy="50" r="22" fill="#0F47AF" />
          <polygon
            points="50,33 54,44 65,44 56,51 60,62 50,55 40,62 44,51 35,44 46,44"
            fill="#FCD116"
            stroke="#0F47AF"
            strokeWidth="0.8"
          />
          <line x1="50" y1="50" x2="50" y2="30" stroke="#FCD116" strokeWidth="1.2" />
          <line x1="50" y1="50" x2="69" y2="44" stroke="#FCD116" strokeWidth="1.2" />
          <line x1="50" y1="50" x2="62" y2="67" stroke="#FCD116" strokeWidth="1.2" />
          <line x1="50" y1="50" x2="38" y2="67" stroke="#FCD116" strokeWidth="1.2" />
          <line x1="50" y1="50" x2="31" y2="44" stroke="#FCD116" strokeWidth="1.2" />
        </svg>
      );

    case "SD": // Sudan
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="none">
          <rect y="0" width="100" height="33.33" fill="#D21034" />
          <rect y="33.33" width="100" height="33.34" fill="#FFFFFF" />
          <rect y="66.67" width="100" height="33.33" fill="#000000" />
          <polygon points="0,0 48,50 0,100" fill="#007229" />
        </svg>
      );

    case "SO": // Somalia
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect width="100" height="100" fill="#4189DD" />
          <polygon points="50,22 57,40 76,40 61,51 67,69 50,57 33,69 39,51 24,40 43,40" fill="#FFFFFF" />
        </svg>
      );

    case "KE": // Kenya
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect y="0" width="100" height="30" fill="#000000" />
          <rect y="30" width="100" height="5" fill="#FFFFFF" />
          <rect y="35" width="100" height="30" fill="#BB162B" />
          <rect y="65" width="100" height="5" fill="#FFFFFF" />
          <rect y="70" width="100" height="30" fill="#006600" />
          <line x1="28" y1="20" x2="72" y2="80" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="72" y1="20" x2="28" y2="80" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
          <ellipse cx="50" cy="50" rx="14" ry="24" fill="#BB162B" stroke="#000000" strokeWidth="1.5" />
          <path d="M50,26 Q40,50 50,74 Q60,50 50,26" fill="#000000" />
          <circle cx="50" cy="50" r="3.5" fill="#FFFFFF" />
        </svg>
      );

    case "ER": // Eritrea
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <polygon points="0,0 100,0 100,50" fill="#12AD2B" />
          <polygon points="0,100 100,100 100,50" fill="#4189DD" />
          <polygon points="0,0 100,50 0,100" fill="#EB181E" />
          <circle cx="34" cy="50" r="14" fill="none" stroke="#FFD100" strokeWidth="2" strokeDasharray="3,1" />
          <line x1="34" y1="36" x2="34" y2="64" stroke="#FFD100" strokeWidth="1.5" />
        </svg>
      );

    case "DJ": // Djibouti
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect y="0" width="100" height="50" fill="#6AB2E7" />
          <rect y="50" width="100" height="50" fill="#12AD2B" />
          <polygon points="0,0 48,50 0,100" fill="#FFFFFF" />
          <polygon points="20,40 24,49 33,49 26,55 29,64 20,58 11,64 14,55 7,49 16,49" fill="#D7141A" />
        </svg>
      );

    case "EG": // Egypt
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="none">
          <rect y="0" width="100" height="33.33" fill="#C8102E" />
          <rect y="33.33" width="100" height="33.34" fill="#FFFFFF" />
          <rect y="66.67" width="100" height="33.33" fill="#000000" />
          <circle cx="50" cy="50" r="8" fill="#C09A3E" />
        </svg>
      );

    case "US": // USA
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect y="0" width="100" height="7.7" fill="#B22234" />
          <rect y="7.7" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="15.4" width="100" height="7.7" fill="#B22234" />
          <rect y="23.1" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="30.8" width="100" height="7.7" fill="#B22234" />
          <rect y="38.5" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="46.2" width="100" height="7.7" fill="#B22234" />
          <rect y="53.9" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="61.6" width="100" height="7.7" fill="#B22234" />
          <rect y="69.3" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="77" width="100" height="7.7" fill="#B22234" />
          <rect y="84.7" width="100" height="7.7" fill="#FFFFFF" />
          <rect y="92.4" width="100" height="7.7" fill="#B22234" />
          <rect x="0" y="0" width="46" height="53.9" fill="#3C3B6E" />
          <circle cx="12" cy="14" r="2.2" fill="#FFF" />
          <circle cx="23" cy="14" r="2.2" fill="#FFF" />
          <circle cx="34" cy="14" r="2.2" fill="#FFF" />
          <circle cx="17" cy="27" r="2.2" fill="#FFF" />
          <circle cx="28" cy="27" r="2.2" fill="#FFF" />
          <circle cx="12" cy="40" r="2.2" fill="#FFF" />
          <circle cx="23" cy="40" r="2.2" fill="#FFF" />
          <circle cx="34" cy="40" r="2.2" fill="#FFF" />
        </svg>
      );

    case "GB": // UK
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect width="100" height="100" fill="#012169" />
          <line x1="0" y1="0" x2="100" y2="100" stroke="#FFFFFF" strokeWidth="16" />
          <line x1="100" y1="0" x2="0" y2="100" stroke="#FFFFFF" strokeWidth="16" />
          <line x1="0" y1="0" x2="100" y2="100" stroke="#C8102E" strokeWidth="6" />
          <line x1="100" y1="0" x2="0" y2="100" stroke="#C8102E" strokeWidth="6" />
          <rect x="42" y="0" width="16" height="100" fill="#FFFFFF" />
          <rect x="0" y="42" width="100" height="16" fill="#FFFFFF" />
          <rect x="45" y="0" width="10" height="100" fill="#C8102E" />
          <rect x="0" y="45" width="100" height="10" fill="#C8102E" />
        </svg>
      );

    case "AE": // UAE
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="none">
          <rect y="0" width="100" height="33.33" fill="#00732F" />
          <rect y="33.33" width="100" height="33.34" fill="#FFFFFF" />
          <rect y="66.67" width="100" height="33.33" fill="#000000" />
          <rect x="0" y="0" width="28" height="100" fill="#FF0000" />
        </svg>
      );

    case "CN": // China
      return (
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <rect width="100" height="100" fill="#EE1C25" />
          <polygon points="20,12 24,24 36,24 26,31 30,42 20,35 10,42 14,31 4,24 16,24" fill="#FFFF00" />
          <circle cx="42" cy="16" r="3" fill="#FFFF00" />
          <circle cx="48" cy="24" r="3" fill="#FFFF00" />
          <circle cx="48" cy="36" r="3" fill="#FFFF00" />
          <circle cx="42" cy="44" r="3" fill="#FFFF00" />
        </svg>
      );

    default:
      // Fallback to high-res flagcdn image if not in custom SVG list
      return (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`https://flagcdn.com/w320/${code.toLowerCase()}.png`}
          alt={code}
          crossOrigin="anonymous"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      );
  }
}

/**
 * Circular Country Flag Badge.
 * Features:
 * - Thick solid white border ring
 * - Soft drop-shadow & high ambient contrast
 * - Renders crisp SVG flags for East Africa and key global partners
 */
export function CountryFlagBadge({
  country = "Ethiopia",
  size = 210,
  borderWidth = 8,
  className = "",
  style = {},
}: CountryFlagProps) {
  const code = resolveCountryCode(country);

  return (
    <div
      className={className}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        border: `${borderWidth}px solid #FFFFFF`,
        boxShadow: "0 18px 48px rgba(0, 0, 0, 0.70), 0 2px 10px rgba(255, 255, 255, 0.22)",
        overflow: "hidden",
        position: "relative",
        backgroundColor: "#07080B",
        boxSizing: "border-box",
        flexShrink: 0,
        ...style,
      }}
    >
      {renderFlagSvg(code)}
    </div>
  );
}
