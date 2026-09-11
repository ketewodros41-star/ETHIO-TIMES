"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  ShieldCheck, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  ArrowUpRight, 
  FileText,
  Layers,
  Scale
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  EventVerificationBadge, 
  VerificationScoreMeter, 
  EventStatusBadge 
} from "@/components/status";
import { relativeTime } from "@/lib/utils";
import type { EventVerificationStatus } from "@/lib/types";

const STATUS_FILTERS: { label: string; value: EventVerificationStatus | "all" | "review" }[] = [
  { label: "All Events", value: "all" },
  { label: "Needs Review", value: "review" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Developing", value: "developing" },
  { label: "Contradicted", value: "contradicted" },
];

export function VerificationContent() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<EventVerificationStatus | "all" | "review">("all");
  const [search, setSearch] = useState("");
  const [clearId, setClearId] = useState<string | null>(null);
  const [clearReason, setClearReason] = useState("");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["verification-desk", filter, search],
    queryFn: () =>
      api.listEvents({
        limit: 50,
        sort: "last_seen",
        search: search || undefined,
        verification_status: filter !== "all" && filter !== "review" ? filter : undefined,
        review_required: filter === "review" ? true : undefined,
      }),
    refetchInterval: 10000,
  });

  const clearReview = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.clearReview(id, reason),
    onSuccess: () => {
      setClearId(null);
      setClearReason("");
      void qc.invalidateQueries({ queryKey: ["verification-desk"] });
      void qc.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;

  const reviewCount = items.filter((e) => e.review_required).length;
  const confirmedCount = items.filter((e) => e.event_verification_status === "confirmed").length;
  const contradictedCount = items.filter((e) => e.event_verification_status === "contradicted").length;

  return (
    <div className="space-y-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-accent-green/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-paper-500">Verified Events</p>
              <p className="mt-1 font-display text-3xl font-semibold text-paper-50">{total}</p>
              <p className="text-xs text-paper-400 mt-0.5">Evidence & claim matrix</p>
            </div>
            <ShieldCheck className="h-8 w-8 text-accent-green/80" />
          </CardContent>
        </Card>

        <Card className="border-gold-500/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-gold-400">Review Required</p>
              <p className="mt-1 font-display text-3xl font-semibold text-gold-400">{reviewCount}</p>
              <p className="text-xs text-paper-400 mt-0.5">Sensitive topic or claim conflict</p>
            </div>
            <ShieldAlert className="h-8 w-8 text-gold-400" />
          </CardContent>
        </Card>

        <Card className="border-green-500/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-green-400">Confirmed Coverage</p>
              <p className="mt-1 font-display text-3xl font-semibold text-green-400">{confirmedCount}</p>
              <p className="text-xs text-paper-400 mt-0.5">Multi-source corroboration</p>
            </div>
            <CheckCircle2 className="h-8 w-8 text-green-400" />
          </CardContent>
        </Card>

        <Card className="border-red-500/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-red-400">Contradictions</p>
              <p className="mt-1 font-display text-3xl font-semibold text-red-400">{contradictedCount}</p>
              <p className="text-xs text-paper-400 mt-0.5">Conflicting statistics/reports</p>
            </div>
            <Scale className="h-8 w-8 text-red-500" />
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1 rounded-card border border-ink-700 bg-ink-850 p-1">
          {STATUS_FILTERS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              className={`px-3 py-1.5 rounded-sm text-xs font-medium transition-colors ${
                filter === tab.value
                  ? "bg-accent-green text-ink-950 font-semibold"
                  : "text-paper-400 hover:text-paper-200 hover:bg-ink-750"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Input
            placeholder="Search claims & events…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56 h-8 text-xs"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 h-8 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin text-accent-green" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Clear Review Dialog Modal */}
      {clearId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <Card className="w-full max-w-md p-6 bg-ink-900 border-ink-700 space-y-4">
            <h3 className="font-display text-lg font-semibold text-paper-50">Clear Editorial Review</h3>
            <p className="text-xs text-paper-400">
              Provide editorial rationale before clearing this review flag. Once cleared, the story becomes eligible for auto-publishing.
            </p>
            <Input
              placeholder="e.g., Verified with primary government press release..."
              value={clearReason}
              onChange={(e) => setClearReason(e.target.value)}
              className="text-sm"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setClearId(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!clearReason.trim() || clearReview.isPending}
                onClick={() => clearReview.mutate({ id: clearId, reason: clearReason })}
              >
                {clearReview.isPending ? "Clearing…" : "Confirm & Clear"}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Event Cards */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-paper-500 py-10 justify-center">
          <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
          <span>Verifying cross-source evidence…</span>
        </div>
      ) : isError ? (
        <Card className="p-6 text-center text-sm text-red-400">
          Failed to load verification feed: {error instanceof Error ? error.message : "Error"}
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-sm text-paper-500">
          No events currently match this verification criteria.
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((e) => (
            <Card key={e.id} className="p-4 transition-colors hover:border-ink-600 bg-ink-900">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <EventVerificationBadge status={e.event_verification_status} />
                    {e.review_required && (
                      <Badge variant="gold" className="flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> Review Required
                      </Badge>
                    )}
                    {e.primary_source_available && (
                      <Badge variant="green">Primary Source</Badge>
                    )}
                    {e.primary_category && (
                      <Badge variant="muted">{e.primary_category}</Badge>
                    )}
                    <span className="text-xs text-paper-500">
                      {relativeTime(e.last_seen_at)}
                    </span>
                  </div>

                  <Link href={`/events/${e.id}`}>
                    <h3 className="font-display text-base font-medium text-paper-50 hover:text-accent-green transition-colors line-clamp-2">
                      {e.title}
                    </h3>
                  </Link>

                  {e.summary && (
                    <p className="mt-1 line-clamp-2 text-xs text-paper-400 leading-relaxed">
                      {e.summary}
                    </p>
                  )}

                  {e.review_reasons && e.review_reasons.length > 0 && (
                    <div className="mt-2 rounded bg-gold-950/20 border border-gold-500/20 px-2.5 py-1 text-[11px] text-gold-300">
                      <span className="font-semibold">Review trigger:</span> {e.review_reasons.join(" · ")}
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-400">
                    <span className="flex items-center gap-1 font-mono">
                      <Layers className="h-3.5 w-3.5 text-paper-500" />
                      {e.article_count} article{e.article_count === 1 ? "" : "s"} across {e.source_count} source{e.source_count === 1 ? "" : "s"}
                    </span>
                    {e.key_entities && e.key_entities.length > 0 && (
                      <span className="text-paper-500 truncate max-w-md">
                        Entities: {e.key_entities.slice(0, 4).join(", ")}
                      </span>
                    )}
                  </div>
                </div>

                {/* Right side: Verification Score Meter & Actions */}
                <div className="flex sm:flex-col items-end justify-between gap-3 shrink-0 border-t md:border-t-0 md:border-l border-ink-800 pt-3 md:pt-0 md:pl-4 min-w-[170px]">
                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-label text-paper-500">Verification Score</p>
                    <div className="mt-1 flex items-center justify-end gap-2">
                      <VerificationScoreMeter score={e.verification_score} />
                      <span className="font-mono text-sm font-semibold text-paper-100">
                        {Math.round(e.verification_score ?? 0)}/100
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    {e.review_required && (
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => setClearId(e.id)}
                        className="h-8 text-xs text-gold-300"
                      >
                        Clear Review
                      </Button>
                    )}
                    <Link href={`/events/${e.id}`}>
                      <Button size="sm" variant="outline" className="h-8 text-xs flex items-center gap-1">
                        Control Desk <ArrowUpRight className="h-3 w-3" />
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
