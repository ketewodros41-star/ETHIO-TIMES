import React from "react";
import { cn } from "@/lib/utils";

export function ETLogoMark({
  size = 40,
  accent = "#22c55e",
  className,
}: {
  size?: number;
  accent?: string;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: "inline-block", verticalAlign: "middle" }}
    >
      {/* Outer Hexagon Shield with crisp geometry */}
      <polygon
        points="50,6 88,28 88,72 50,94 12,72 12,28"
        stroke="#FFFFFF"
        strokeWidth="6.5"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Monogram E (Left side) */}
      <path
        d="M32 32 H47 M32 50 H44 M32 68 H47 M32 32 V68"
        stroke="#FFFFFF"
        strokeWidth="6"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      {/* Monogram T (Right side) */}
      <path
        d="M52 32 H78 M65 32 V68"
        stroke="#FFFFFF"
        strokeWidth="6"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      {/* Subtle brand accent mark */}
      <circle cx="77" cy="68" r="3" fill={accent} />
    </svg>
  );
}

export function EthiopianTimesBrand({
  markSize = 36,
  accent = "#22c55e",
  layout = "stacked",
  className,
}: {
  markSize?: number;
  accent?: string;
  layout?: "stacked" | "inline";
  className?: string;
}) {
  if (layout === "inline") {
    return (
      <div className={cn("flex items-center gap-2.5 font-display select-none", className)}>
        <ETLogoMark size={markSize} accent={accent} />
        <div className="flex items-baseline gap-1 text-base font-extrabold tracking-tight text-paper-50">
          <span>ETHIOPIAN</span>
          <span className="text-paper-300">TIMES</span>
          <span style={{ color: accent }}>.</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-3 font-display select-none", className)}>
      <ETLogoMark size={markSize} accent={accent} />
      <div className="flex flex-col leading-[0.92] text-left font-black tracking-wider text-paper-50">
        <span className="text-[13px] tracking-[0.08em] text-paper-50">ETHIOPIAN</span>
        <span className="text-[13px] tracking-[0.08em] text-paper-300">TIMES</span>
      </div>
    </div>
  );
}
