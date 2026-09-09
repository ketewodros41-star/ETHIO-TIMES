import { cn } from "@/lib/utils";

export function Wordmark({
  className,
  showTick = true,
}: {
  className?: string;
  showTick?: boolean;
}) {
  return (
    <span
      className={cn(
        "font-display text-lg font-bold tracking-tight text-paper-50",
        className,
      )}
    >
      ETHIO
      <span className="text-paper-300">TIMES</span>
      {showTick && <span className="ml-1 text-accent-green">.</span>}
    </span>
  );
}
