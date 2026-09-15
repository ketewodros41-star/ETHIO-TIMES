"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Bell, Clock, Layers, Palette, Play, RefreshCw, ShieldAlert, TrendingUp, Users, Zap } from "lucide-react";
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
import { formatDate, relativeTime } from "@/lib/utils";
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

const NEWS_BEATS: { id: string; label: string; icon: string }[] = [
  { id: "", label: "All Beats", icon: "🌐" },
  { id: "politics", label: "Politics", icon: "🏛️" },
  { id: "economy", label: "Economy & Business", icon: "📈" },
  { id: "sports", label: "Sports", icon: "⚽" },
  { id: "technology", label: "Tech & Innovation", icon: "🤖" },
  { id: "culture", label: "Culture & Society", icon: "🎭" },
  { id: "conflict", label: "Security & Conflict", icon: "🛡️" },
  { id: "breaking", label: "Breaking", icon: "⚡" },
  { id: "diplomacy", label: "Regional Diplomacy", icon: "🤝" },
  { id: "humanitarian", label: "Humanitarian", icon: "🕊️" },
];

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "last_seen", label: "🆕 Latest News" },
  { value: "trend_score", label: "🔥 Hottest Trends" },
  { value: "verification_score", label: "🛡️ Highest Verification" },
  { value: "article_count", label: "📰 Most Covered (Depth)" },
];

export function EventsContent() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [category, setCategory] = useState("");
  const [verification, setVerification] = useState<EventVerificationStatus | "">("");
  const [trend, setTrend] = useState<TrendStatus | "">("");
  const [breakingOnly, setBreakingOnly] = useState(false);
  const [reviewOnly, setReviewOnly] = useState(false);
  const [sort, setSort] = useState<string>("last_seen");
  const [scope, setScope] = useState<"ethiopia" | "neighboring" | "international" | "all">("ethiopia");

  const { hasNew, newCount, dismiss, refresh } = useNewEventsPoller(() => {
    qc.invalidateQueries({ queryKey: ["events"] });
  });

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["events", search, page, category, verification, trend, breakingOnly, reviewOnly, sort, scope],
    queryFn: () =>
      api.listEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
        category: category || undefined,
        verification_status: verification || undefined,
        trend_status: trend || undefined,
        review_required: reviewOnly ? true : undefined,
        breaking: breakingOnly ? true : undefined,
        sort,
        scope,
      }),
    refetchInterval: 120_000,
    refetchIntervalInBackground: false,
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
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      {/* Top action / notification toast */}
      {hasNew && (
        <div className="flex items-center justify-between p-3 rounded-card bg-accent-green/10 border border-accent-green/30 text-accent-green text-xs animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-green"></span>
            </span>
            <span>
              <strong>{newCount} new event{newCount > 1 ? "s" : ""}</strong> detected from live media feeds.
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { refresh(); refetch(); }}
              className="px-2.5 py-1 rounded bg-accent-green text-ink-950 font-semibold hover:bg-accent-green/90 transition"
            >
              Show Latest
            </button>
            <button
              onClick={dismiss}
              className="px-1.5 py-1 text-paper-400 hover:text-paper-200"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Regional Scope Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-white/[0.08]">
        <div className="flex items-center gap-1 p-1 rounded-card bg-ink-900/80 border border-white/[0.08] backdrop-blur-xs shadow-xs w-fit">
          <button
            type="button"
            onClick={() => { setScope("ethiopia"); setPage(0); }}
            className={`px-3.5 py-1.5 rounded-card text-xs font-medium transition-all duration-150 ${
              scope === "ethiopia"
                ? "bg-accent-green text-ink-950 font-bold shadow-sm"
                : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
            }`}
          >
            🇪🇹 Ethiopia & Diaspora
          </button>
          <button
            type="button"
            onClick={() => { setScope("neighboring"); setPage(0); }}
            className={`px-3.5 py-1.5 rounded-card text-xs font-medium transition-all duration-150 ${
              scope === "neighboring"
                ? "bg-accent-green text-ink-950 font-bold shadow-sm"
                : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
            }`}
          >
            🌍 Horn of Africa & Neighbors
          </button>
          <button
            type="button"
            onClick={() => { setScope("international"); setPage(0); }}
            className={`px-3.5 py-1.5 rounded-card text-xs font-medium transition-all duration-150 ${
              scope === "international"
                ? "bg-accent-green text-ink-950 font-bold shadow-sm"
                : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
            }`}
          >
            🌐 International
          </button>
          <button
            type="button"
            onClick={() => { setScope("all"); setPage(0); }}
            className={`px-3.5 py-1.5 rounded-card text-xs font-medium transition-all duration-150 ${
              scope === "all"
                ? "bg-accent-green text-ink-950 font-bold shadow-sm"
                : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
            }`}
          >
            ✨ All Coverage
          </button>
        </div>
        <div className="flex items-center gap-3">
          {category && (
            <button
              onClick={() => { setCategory(""); setPage(0); }}
              className="text-xs text-accent-green hover:underline flex items-center gap-1 font-mono font-medium"
            >
              Reset Beat (×)
            </button>
          )}
          <span className="text-xs text-paper-400 font-mono bg-ink-900/60 border border-white/[0.06] px-2.5 py-1 rounded-full">
            <strong className="text-paper-100">{total}</strong> events in view
          </span>
        </div>
      </div>

      {/* Newsroom Beat / Category Filter Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none pt-0.5">
        <span className="text-[11px] font-mono text-paper-500 uppercase tracking-wider shrink-0 mr-1">
          Beats:
        </span>
        {NEWS_BEATS.map((beat) => {
          const isActive = category === beat.id;
          return (
            <button
              key={beat.id}
              type="button"
              onClick={() => {
                setCategory(beat.id);
                setPage(0);
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all border ${
                isActive
                  ? "bg-accent-green text-ink-950 border-accent-green font-bold shadow-sm"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border-ink-700/80"
              }`}
            >
              <span>{beat.icon}</span>
              <span>{beat.label}</span>
            </button>
          );
        })}
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
              setSort(e.target.value);
            }}
            className="h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-xs text-paper-300 font-medium"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
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
        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono text-paper-400 bg-ink-850 border border-ink-700 px-2.5 py-1 rounded-full mr-1">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-green animate-pulse" />
            Live Sync: 2m
          </span>
          <span className="text-xs text-paper-500 mr-1">{total} clustered events</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending}
            className="flex items-center gap-1.5 border-accent-green/50 text-accent-green hover:bg-accent-green/10"
            title="Immediately fetch new articles from Tikvah and active RSS sources and cluster into events"
          >
            <Play className={`h-3.5 w-3.5 ${ingestMutation.isPending ? "animate-spin" : ""}`} />
            {ingestMutation.isPending ? "Syncing Feeds…" : "Sync Feeds"}
          </Button>
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

      <div className="space-y-3.5">
        {items.map((e) => {
          const accentBorder = e.breaking_candidate
            ? "border-l-4 border-l-signal-red hover:border-l-signal-red"
            : e.trend_status === "high_priority" || e.trend_status === "trending"
              ? "border-l-4 border-l-accent-gold hover:border-l-accent-gold"
              : e.event_verification_status === "confirmed"
                ? "border-l-4 border-l-accent-green hover:border-l-accent-green"
                : "border-l-4 border-l-white/[0.12] hover:border-l-white/[0.3]";

          return (
            <Link key={e.id} href={`/events/${e.id}`} className="group block">
              <div
                className={`card-editorial relative overflow-hidden rounded-card p-5 sm:p-5.5 ${accentBorder}`}
              >
                <div className="flex flex-col md:flex-row items-start justify-between gap-5">
                  <div className="min-w-0 flex-1">
                    {/* Badge Row */}
                    <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
                      <TrendStatusBadge status={e.trend_status} />
                      {e.breaking_candidate && (
                        <Badge variant="red">⚡ breaking candidate</Badge>
                      )}
                      <EventVerificationBadge status={e.event_verification_status} />
                      <EventStatusBadge status={e.status} />
                      {e.review_required && (
                        <Badge variant="gold">human review</Badge>
                      )}
                      {e.primary_category && (
                        <Badge variant="default">{e.primary_category}</Badge>
                      )}
                      {e.primary_region && (
                        <Badge variant="muted">📍 {e.primary_region}</Badge>
                      )}
                    </div>

                    {/* Headline */}
                    <h3 className="font-display text-[18px] sm:text-[20px] font-bold leading-snug tracking-tight text-paper-50 group-hover:text-accent-green transition-colors">
                      {e.title}
                    </h3>

                    {/* Summary */}
                    {e.summary && (
                      <p className="mt-2 line-clamp-2 text-[13.5px] leading-relaxed text-paper-300/85">
                        {e.summary}
                      </p>
                    )}

                    {/* Metadata Strip */}
                    <div className="mt-3.5 flex flex-wrap items-center gap-4 text-xs text-paper-400">
                      <span className="inline-flex items-center gap-1 font-mono text-[11px]">
                        <Layers className="h-3 w-3 text-paper-500" /> {e.article_count} articles
                      </span>
                      <span className="inline-flex items-center gap-1 font-mono text-[11px]">
                        <Users className="h-3 w-3 text-paper-500" /> {e.source_count} sources
                      </span>
                      <span className="inline-flex items-center gap-1 font-mono text-[11px]">
                        <TrendingUp className="h-3 w-3 text-accent-gold" /> trend {Math.round(e.trend_score)}
                      </span>
                      {e.breaking_candidate && (
                        <span className="inline-flex items-center gap-1 text-signal-red font-mono text-[11px]">
                          <Zap className="h-3 w-3" /> velocity burst
                        </span>
                      )}
                      <span
                        title={formatDate(e.last_seen_at ?? e.first_seen_at ?? e.created_at)}
                        className="inline-flex items-center gap-1 font-mono text-[11px] text-paper-400"
                      >
                        <Clock className="h-3 w-3 text-paper-500" />
                        {relativeTime(e.last_seen_at ?? e.first_seen_at ?? e.created_at)}
                      </span>
                      <span
                        onClick={(ev) => {
                          ev.preventDefault();
                          window.location.href = `/studio/templates?event_id=${e.id}`;
                        }}
                        className="inline-flex items-center gap-1.5 rounded-full bg-accent-green/10 border border-accent-green/30 px-2.5 py-0.5 text-accent-green hover:bg-accent-green/20 transition-colors cursor-pointer text-xs font-semibold font-mono"
                      >
                        <Palette className="h-3 w-3" /> Studio Card →
                      </span>
                    </div>
                  </div>

                  {/* Right Intelligence Metrics Column */}
                  <div className="shrink-0 flex md:flex-col items-center md:items-end justify-between w-full md:w-auto pt-2 md:pt-0 border-t md:border-t-0 border-white/[0.06]">
                    <div className="flex items-center md:flex-col md:items-end gap-2 md:gap-0">
                      <div className="font-mono text-[10px] uppercase tracking-wider text-paper-500">trend</div>
                      <div className="font-display text-2xl font-bold tabular-nums text-paper-50">
                        {Math.round(e.trend_score)}
                      </div>
                    </div>
                    <div className="mt-1 flex justify-end">
                      <TrendScoreMeter score={e.trend_score} />
                    </div>
                    <div className="mt-3 font-mono text-[10px] uppercase tracking-wider text-paper-500">
                      verification
                    </div>
                    <div className="mt-1 flex justify-end">
                      <VerificationScoreMeter score={e.verification_score} />
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
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
