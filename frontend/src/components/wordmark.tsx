import { cn } from "@/lib/utils";
import { ETLogoMark } from "@/components/et-logo";

export function Wordmark({
  className,
  showIcon = true,
  showTick = true,
  iconSize = 28,
}: {
  className?: string;
  showIcon?: boolean;
  showTick?: boolean;
  iconSize?: number;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2.5 font-display text-base font-extrabold tracking-tight text-paper-50 select-none",
        className,
      )}
    >
      {showIcon && <ETLogoMark size={iconSize} accent="#22c55e" />}
      <span className="flex items-baseline gap-1">
        <span>ETHIOPIAN</span>
        <span className="text-paper-300">TIMES</span>
        {showTick && <span className="text-accent-green">.</span>}
      </span>
    </span>
  );
}
