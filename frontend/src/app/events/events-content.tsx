"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Bell, Layers, Palette, Play, RefreshCw, ShieldAlert, TrendingUp, Users, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useNewEventsPoller } from "@/lib/useNewEventsPoller";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  EventStatusBadge,
  EventVerificationBadge,
  TrendScoreMeter,
  TrendStatusBadge,
  VerificationScoreMeter,
} from "@/components/status";
import { relativeTime } from "@/lib/utils";
import type { EventVerificationStatus, TrendStatus } from "@/lib/types";

const PAGE_SIZE = 25;

const VERIFY_FILTERS: { value: EventVerificationStatus | ""; label: string }[] = [
  { value: "", label: "All verification" },
  { value: "unverified", label: "Unverified" },
  { value: "developing", label: "Developing" },
  { value: "partially_confirmed", label: "Partially confirmed" },
  { value: "confirmed", label: "Confirmed" },
  { value: "contradicted", label: "Contradicted" },
];

const TREND_FILTERS: { value: TrendStatus | ""; label: string }[] = [
  { value: "", label: "All trends" },
  { value: "breaking", label: "Breaking" },
  { value: "high_priority", label: "High priority" },
  { value: "trending", label: "Trending" },
  { value: "emerging", label: "Emerging" },
  { value: "low", label: "Low" },
];

export function EventsContent() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [verification, setVerification] = useState<EventVerificationStatus | "">("");
  const [trend, setTrend] = useState<TrendStatus | "">("");
  const [breakingOnly, setBreakingOnly] = useState(false);
  const [reviewOnly, setReviewOnly] = useState(false);
  const [sort, setSort] = useState<"last_seen" | "trend_score">("trend_score");
  const [scope, setScope] = useState<"ethiopia" | "neighboring" | "all">("ethiopia");

  const { hasNew, newCount, dismiss, refresh } = useNewEventsPoller(() => {
    qc.invalidateQueries({ queryKey: ["events"] });
  });

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["events", search, page, verification, trend, breakingOnly, reviewOnly, sort, scope],
    queryFn: () =>
      api.listEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
        verification_status: verification || undefined,
        trend_status: trend || undefined,
        review_required: reviewOnly ? true : undefined,
        breaking: breakingOnly ? true : undefined,
        sort,
        scope,
      }),
    refetchInterval: 60000,
  });

  const ingestMutation = useMutation({
    mutationFn: () => api.triggerIngest(),
    onSuccess: () => {
      setTimeout(() => refetch(), 2000);
      setTimeout(() => refetch(), 5000);
    },
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <div className="space-y-4">
      {hasNew && (
        <div className="flex items-center justify-between rounded-card border border-amber-700/50 bg-amber-950/30 px-4 py-2.5 text-xs text-amber-300">
          <div className="flex items-center gap-2">
            <Bell className="h-3.5 w-3.5 animate-pulse" />
            <span><strong>{newCount} new event{newCount !== 1 ? "s" : ""}</strong> available since you last loaded</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={refresh} className="px-3 py-1 rounded-card bg-amber-700/40 hover:bg-amber-700/60 font-semibold text-amber-200 transition-colors">
              Refresh
            </button>
            <button onClick={dismiss} className="text-amber-500 hover:text-amber-300 transition-colors">✕</button>
          </div>
        </div>
      )}

      {/* Regional Scope Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-1 border-b border-ink-800">
        <div className="flex items-center gap-1.5 p-1 rounded-card bg-ink-850 border border-ink-700 w-fit">
          <button
            type="button"
            onClick={() => { setScope("ethiopia"); setPage(0); }}
            className={`px-3 py-1.5 rounded-card text-xs font-medium transition-all ${
              scope === "ethiopia"
                ? "bg-accent-green text-ink-950 font-semibold shadow-sm"
                : "text-paper-400 hover:text-paper-100"
            }`}
          >
            🇪🇹 Ethiopia & Diaspora
          </button>
          <button
            type="button"
            onClick={() => { setScope("neighboring"); setPage(0); }}
            className={`px-3 py-1.5 rounded-card text-xs font-medium transition-all ${
              scope === "neighboring"
                ? "bg-accent-green text-ink-950 font-semibold shadow-sm"
                : "text-paper-400 hover:text-paper-100"
            }`}
          >
            🌍 Horn of Africa & Neighbors
          </button>
          <button
            type="button"
            onClick={() => { setScope("all"); setPage(0); }}
            className={`px-3 py-1.5 rounded-card text-xs font-medium transition-all ${
              scope === "all"
                ? "bg-accent-green text-ink-950 font-semibold shadow-sm"
                : "text-paper-400 hover:text-paper-100"
            }`}
          >
            🌐 All Coverage
          </button>
        </div>
        <span className="text-xs text-paper-500 font-mono">
          {total} events in view
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Search events…"
            value={search}
            onChange={(e) => {
              setPage(0);
              setSearch(e.target.value);
            }}
            className="max-w-sm"
          />
          <select
            value={verification}
            onChange={(e) => {
              setPage(0);
              setVerification(e.target.value as EventVerificationStatus | "");
            }}
            className="h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-xs text-paper-300"
          >
            {VERIFY_FILTERS.map((opt) => (
              <option key={opt.label} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={trend}
            onChange={(e) => {
              setPage(0);
              setTrend(e.target.value as TrendStatus | "");
            }}
            className="h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-xs text-paper-300"
          >
            {TREND_FILTERS.map((opt) => (
              <option key={opt.label} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(e) => {
              setPage(0);
              setSort(e.target.value as "last_seen" | "trend_score");
            }}
            className="h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-xs text-paper-300"
          >
            <option value="trend_score">Sort by trend score</option>
            <option value="last_seen">Sort by last seen</option>
          </select>
          <label className="inline-flex items-center gap-2 text-xs text-paper-300">
            <input
              type="checkbox"
              checked={breakingOnly}
              onChange={(e) => {
                setPage(0);
                setBreakingOnly(e.target.checked);
              }}
            />
            Breaking candidates
          </label>
          <label className="inline-flex items-center gap-2 text-xs text-paper-300">
            <input
              type="checkbox"
              checked={reviewOnly}
              onChange={(e) => {
                setPage(0);
                setReviewOnly(e.target.checked);
              }}
            />
            Review required
          </label>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-paper-500">{total} clustered events</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin text-accent-green" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {isError && (
        <Card className="border-red-500/30 bg-red-950/20 p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Failed to load events: {error instanceof Error ? error.message : "Unknown error"}</span>
            </div>
            <Button size="sm" variant="subtle" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        </Card>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-paper-500 py-6">
          <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
          <span>Loading events…</span>
        </div>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <Card className="p-8 text-center space-y-3">
          <p className="text-sm text-paper-400">
            No events match your current filter. If you just ingested sources, the intelligence pipeline is clustering them into events.
          </p>
          <div className="flex justify-center gap-2">
            <Button
              size="sm"
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
              className="flex items-center gap-1.5"
            >
              <Play className="h-3.5 w-3.5" />
              {ingestMutation.isPending ? "Ingesting & Clustering…" : "Ingest & Cluster Active Feeds"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh Now
            </Button>
          </div>
        </Card>
      )}

      <div className="space-y-3">
        {items.map((e) => (
          <Link key={e.id} href={`/events/${e.id}`}>
            <Card className="p-4 transition-colors hover:border-ink-600">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <TrendStatusBadge status={e.trend_status} />
                    {e.breaking_candidate && (
                      <Badge variant="red">breaking candidate</Badge>
                    )}
                    <EventVerificationBadge status={e.event_verification_status} />
                    <EventStatusBadge status={e.status} />
                    {e.review_required && (
                      <Badge variant="gold">review required</Badge>
                    )}
                    {e.primary_source_available && (
                      <Badge variant="green">primary source</Badge>
                    )}
                    {e.primary_category && (
                      <Badge variant="default">{e.primary_category}</Badge>
                    )}
                    {e.primary_region && (
                      <Badge variant="muted">{e.primary_region}</Badge>
                    )}
                  </div>
                  <h3 className="font-display text-lg font-medium leading-snug text-paper-50">
                    {e.title}
                  </h3>
                  {e.summary && (
                    <p className="mt-1 line-clamp-2 text-sm text-paper-300">
                      {e.summary}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-500">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="h-3 w-3" /> {e.article_count} articles
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3 w-3" /> {e.source_count} sources
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <TrendingUp className="h-3 w-3" /> trend {Math.round(e.trend_score)}
                    </span>
                    {e.breaking_candidate && (
                      <span className="inline-flex items-center gap-1 text-signal-red">
                        <Zap className="h-3 w-3" /> velocity burst
                      </span>
                    )}
                    {e.review_required && (
                      <span className="inline-flex items-center gap-1 text-accent-gold">
                        <ShieldAlert className="h-3 w-3" /> human review
                      </span>
                    )}
                    <span>updated {relativeTime(e.last_seen_at)}</span>
                    <span
                      onClick={(ev) => {
                        ev.preventDefault();
                        window.location.href = `/studio/templates?event_id=${e.id}`;
                      }}
                      className="inline-flex items-center gap-1 rounded bg-ink-800 px-2 py-0.5 text-accent-green hover:bg-ink-700 transition-colors cursor-pointer text-xs font-medium"
                    >
                      <Palette className="h-3 w-3" /> Photo Studio →
                    </span>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-mono text-xs text-paper-500">trend</div>
                  <div className="font-display text-2xl tabular-nums text-paper-50">
                    {Math.round(e.trend_score)}
                  </div>
                  <div className="mt-1 flex justify-end">
                    <TrendScoreMeter score={e.trend_score} />
                  </div>
                  <div className="mt-2 font-mono text-[10px] uppercase tracking-label text-paper-500">
                    verification {e.verification_score}
                  </div>
                  <div className="mt-1 flex justify-end">
                    <VerificationScoreMeter score={e.verification_score} />
                  </div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            className="rounded-card border border-ink-600 px-3 py-1 text-xs disabled:opacity-40"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </button>
          <span className="text-xs text-paper-500">
            Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}
          </span>
          <button
            className="rounded-card border border-ink-600 px-3 py-1 text-xs disabled:opacity-40"
            disabled={(page + 1) * PAGE_SIZE >= total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
