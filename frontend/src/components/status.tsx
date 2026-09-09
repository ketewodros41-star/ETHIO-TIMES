import { Badge } from "@/components/ui/badge";
import type {
  ArticleStatus,
  SourceHealthStatus,
  VerificationStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const HEALTH_COLOR: Record<SourceHealthStatus, string> = {
  healthy: "bg-accent-green",
  degraded: "bg-accent-gold",
  failing: "bg-signal-red",
  disabled: "bg-paper-500",
  unknown: "bg-ink-600",
};

export function HealthDot({ status }: { status: SourceHealthStatus }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className={cn("h-2 w-2 rounded-full", HEALTH_COLOR[status])} />
      <span className="text-xs capitalize text-paper-300">{status}</span>
    </span>
  );
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  if (status === "verified") return <Badge variant="green">verified</Badge>;
  if (status === "needs_verification")
    return <Badge variant="gold">needs verification</Badge>;
  return <Badge variant="muted">unverified</Badge>;
}

export function ArticleStatusBadge({ status }: { status: ArticleStatus }) {
  const variant =
    status === "normalized"
      ? "green"
      : status === "duplicate"
        ? "muted"
        : status === "discarded"
          ? "red"
          : "default";
  return <Badge variant={variant}>{status}</Badge>;
}

export function RelevanceMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8 ? "bg-accent-green" : score >= 0.5 ? "bg-accent-gold" : "bg-ink-600";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-700">
        <div className={cn("h-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-paper-500">{pct}</span>
    </div>
  );
}
