"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { 
  Zap, 
  Flame, 
  TrendingUp, 
  RefreshCw, 
  ArrowUpRight, 
  Send, 
  ShieldAlert, 
  Layers,
  Sparkles,
  BarChart3
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  TrendScoreMeter, 
  TrendStatusBadge, 
  EventVerificationBadge, 
  EventStatusBadge 
} from "@/components/status";
import { relativeTime } from "@/lib/utils";
import type { TrendStatus } from "@/lib/types";

const TABS: { label: string; value: TrendStatus | "all" | "breaking" }[] = [
  { label: "All Stories", value: "all" },
  { label: "Breaking", value: "breaking" },
  { label: "Trending", value: "trending" },
  { label: "Emerging", value: "emerging" },
  { label: "High Priority", value: "high_priority" },
];

export function TrendsContent() {
  const [activeTab, setActiveTab] = useState<TrendStatus | "all" | "breaking">("all");
  const [search, setSearch] = useState("");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["trends-feed", activeTab, search],
    queryFn: () =>
      api.listEvents({
        limit: 50,
        sort: "trend_score",
        search: search || undefined,
        trend_status: activeTab !== "all" && activeTab !== "breaking" ? activeTab : undefined,
        breaking: activeTab === "breaking" ? true : undefined,
      }),
    refetchInterval: 10000,
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;

  const breakingCount = items.filter((e) => e.breaking_candidate || e.trend_status === "breaking").length;
  const highVelocityCount = items.filter((e) => (e.trend_score ?? 0) >= 50).length;

  return (
    <div className="space-y-6">
      {/* Top Velocity Radar Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-accent-green/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-paper-500">Live Trend Feed</p>
              <p className="mt-1 font-display text-3xl font-semibold text-paper-50">{total}</p>
              <p className="text-xs text-paper-400 mt-0.5">Scored by velocity & importance</p>
            </div>
            <Zap className="h-8 w-8 text-accent-green/80" />
          </CardContent>
        </Card>

        <Card className="border-red-500/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-red-400">Breaking Candidates</p>
              <p className="mt-1 font-display text-3xl font-semibold text-red-400">{breakingCount}</p>
              <p className="text-xs text-paper-400 mt-0.5">Velocity spike candidates</p>
            </div>
            <Flame className="h-8 w-8 text-red-500" />
          </CardContent>
        </Card>

        <Card className="border-gold-500/30 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-gold-400">High Velocity Surge</p>
              <p className="mt-1 font-display text-3xl font-semibold text-gold-400">{highVelocityCount}</p>
              <p className="text-xs text-paper-400 mt-0.5">Trend score ≥ 50</p>
            </div>
            <TrendingUp className="h-8 w-8 text-gold-400" />
          </CardContent>
        </Card>

        <Card className="border-ink-700 bg-ink-850">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-label text-paper-500">Social Automation</p>
              <p className="mt-1 font-display text-3xl font-semibold text-accent-green">Ready</p>
              <p className="text-xs text-paper-400 mt-0.5">Instagram Card Pipeline active</p>
            </div>
            <Sparkles className="h-8 w-8 text-accent-green/70" />
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs & Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1 rounded-card border border-ink-700 bg-ink-850 p-1">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`px-3 py-1.5 rounded-sm text-xs font-medium transition-colors ${
                activeTab === tab.value
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
            placeholder="Search trend radar…"
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

      {/* Event List */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-paper-500 py-10 justify-center">
          <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
          <span>Tracking velocity signals…</span>
        </div>
      ) : isError ? (
        <Card className="p-6 text-center text-sm text-red-400">
          Failed to load trend feed: {error instanceof Error ? error.message : "Error"}
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-sm text-paper-500">
          No events currently match this trend criteria.
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((e) => (
            <Card key={e.id} className="p-4 transition-colors hover:border-ink-600 bg-ink-900">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <TrendStatusBadge status={e.trend_status} />
                    {e.breaking_candidate && (
                      <Badge variant="red" className="animate-pulse">
                        <Flame className="h-3 w-3 mr-1" /> breaking burst
                      </Badge>
                    )}
                    <EventVerificationBadge status={e.event_verification_status} />
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

                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-400">
                    <span className="flex items-center gap-1 font-mono">
                      <Layers className="h-3.5 w-3.5 text-paper-500" />
                      {e.article_count} article{e.article_count === 1 ? "" : "s"} from {e.source_count} source{e.source_count === 1 ? "" : "s"}
                    </span>
                    {e.key_entities && e.key_entities.length > 0 && (
                      <span className="text-paper-500 truncate max-w-md">
                        Entities: {e.key_entities.slice(0, 3).join(", ")}
                      </span>
                    )}
                  </div>
                </div>

                {/* Right side: Trend Score Meter & Actions */}
                <div className="flex sm:flex-col items-end justify-between gap-3 shrink-0 border-t md:border-t-0 md:border-l border-ink-800 pt-3 md:pt-0 md:pl-4 min-w-[150px]">
                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-label text-paper-500">Trend Score</p>
                    <div className="mt-1 flex items-center justify-end gap-2">
                      <TrendScoreMeter score={e.trend_score} />
                      <span className="font-mono text-sm font-semibold text-paper-100">
                        {Math.round(e.trend_score ?? 0)}/100
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mt-2">
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
