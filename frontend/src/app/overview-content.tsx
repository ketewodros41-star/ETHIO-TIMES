"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Radio,
  Newspaper,
  Layers,
  ShieldCheck,
  Zap,
  Send,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Activity,
  CheckCircle2,
} from "lucide-react";
import { api, postsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  EventStatusBadge,
  EventVerificationBadge,
  HealthDot,
  RelevanceMeter,
  TrendStatusBadge,
  TrendScoreMeter,
} from "@/components/status";
import { formatDate, relativeTime } from "@/lib/utils";

function Stat({
  label,
  value,
  hint,
  icon: Icon,
  accentColor = "emerald",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  accentColor?: "emerald" | "amber" | "crimson" | "blue" | "default";
}) {
  const accentClasses = {
    emerald: "text-accent-green bg-accent-green/10 border-accent-green/30",
    amber: "text-accent-gold bg-accent-gold/10 border-accent-gold/30",
    crimson: "text-signal-red bg-signal-red/10 border-signal-red/30",
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    default: "text-paper-300 bg-white/[0.05] border-white/[0.1]",
  }[accentColor];

  return (
    <div className="card-editorial relative overflow-hidden rounded-card p-4.5">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono font-medium uppercase tracking-wider text-paper-400">
          {label}
        </p>
        {Icon && (
          <div className={`flex h-7 w-7 items-center justify-center rounded-md border ${accentClasses}`}>
            <Icon className="h-3.5 w-3.5" />
          </div>
        )}
      </div>
      <p className="mt-2.5 font-display text-3xl sm:text-4xl font-bold tracking-tight text-paper-50 tabular-nums">
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-paper-400/80 font-mono truncate">{hint}</p>}
    </div>
  );
}

export function OverviewContent() {
  const sources = useQuery({
    queryKey: ["sources", "all"],
    queryFn: () => api.listSources({ limit: 200 }),
  });
  const articles = useQuery({
    queryKey: ["articles", "recent"],
    queryFn: () => api.listArticles({ limit: 8 }),
  });
  const health = useQuery({ queryKey: ["source-health"], queryFn: api.sourceHealth });
  const stats = useQuery({ queryKey: ["pipeline-stats"], queryFn: api.pipelineStats });
  const posts = useQuery({
    queryKey: ["posts", "overview"],
    queryFn: () => postsApi.list({ limit: 100 }),
  });
  const events = useQuery({
    queryKey: ["events", "recent"],
    queryFn: () => api.listEvents({ limit: 6, sort: "trend_score" }),
  });
  const breaking = useQuery({
    queryKey: ["events", "breaking"],
    queryFn: () => api.listEvents({ limit: 5, breaking: true, sort: "trend_score" }),
  });
  const trending = useQuery({
    queryKey: ["events", "trending"],
    queryFn: () =>
      api.listEvents({ limit: 5, trend_status: "trending", sort: "trend_score" }),
  });

  const srcItems = sources.data?.items ?? [];
  const activeCount = srcItems.filter((s) => s.is_active).length;
  const healthy = (health.data ?? []).filter((h) => h.health_status === "healthy").length;
  const clustered = stats.data?.by_processing_status.clustered ?? 0;

  const postItems = posts.data?.items ?? [];
  const draftsCount = postItems.filter((p) => p.status === "draft").length;
  const renderedCount = postItems.filter((p) => p.status === "rendered").length;
  const publishedCount = postItems.filter((p) => p.status === "published").length;


  return (
    <div className="space-y-6">
      {/* Executive Metric Strip */}
      <div className="grid grid-cols-2 gap-3.5 sm:gap-4 lg:grid-cols-6">
        <Stat
          label="Sources"
          value={sources.data?.meta.total ?? "—"}
          hint={`${activeCount} active · ${healthy} healthy`}
          icon={Radio}
          accentColor="blue"
        />
        <Stat
          label="Articles"
          value={stats.data?.total_articles ?? articles.data?.meta.total ?? "—"}
          hint={stats.data ? `${stats.data.embedded} embedded` : undefined}
          icon={Newspaper}
          accentColor="default"
        />
        <Stat
          label="Events clustered"
          value={stats.data?.total_events ?? "—"}
          hint={`${clustered} clustered`}
          icon={Layers}
          accentColor="emerald"
        />
        <Stat
          label="Ethiopia-relevant"
          value={stats.data?.ethiopia_related ?? "—"}
          hint="passed AI relevance"
          icon={CheckCircle2}
          accentColor="emerald"
        />
        <Stat
          label="Needs review"
          value={stats.data?.review_required_events ?? "—"}
          hint="sensitive / contradictory"
          icon={ShieldCheck}
          accentColor="amber"
        />
        <Stat
          label="Breaking"
          value={stats.data?.breaking_candidates ?? "—"}
          hint="velocity bursts"
          icon={Zap}
          accentColor="crimson"
        />
      </div>

      {/* Autonomous Publishing Operations Desk */}
      <div className="card-editorial relative overflow-hidden rounded-card p-5 border-accent-green/30 bg-gradient-to-r from-ink-900 via-ink-850 to-ink-900 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="flex h-2 w-2 rounded-full bg-accent-green animate-pulse" />
              <span className="text-xs uppercase font-mono tracking-widest text-accent-green font-bold">
                Automated Dispatch & Publishing Desk
              </span>
              <Badge variant="green">Active</Badge>
              <Badge variant="muted">{postItems.length} Total Posts</Badge>
            </div>
            <p className="text-xs text-paper-300 font-sans">
              Autonomous multi-channel news publishing to Telegram channel & Instagram with bilingual ad-filtering and fact-check verification.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="px-3 py-1.5 rounded-card bg-ink-950/80 border border-white/[0.08] text-paper-300">
                <strong className="text-paper-100 font-bold">{draftsCount}</strong> Drafts
              </span>
              <span className="px-3 py-1.5 rounded-card bg-ink-950/80 border border-white/[0.08] text-paper-300">
                <strong className="text-paper-100 font-bold">{renderedCount}</strong> Rendered
              </span>
              <span className="px-3 py-1.5 rounded-card bg-accent-green/10 border border-accent-green/30 text-accent-green">
                <strong className="font-bold">{publishedCount}</strong> Published
              </span>
            </div>

            <Link
              href="/posts"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-card text-xs font-semibold bg-accent-green text-ink-950 hover:bg-accent-green-hover transition-colors shadow-sm font-mono"
            >
              <Send className="h-3.5 w-3.5" /> Open Publishing Desk
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Breaking Candidates */}
        <div className="card-editorial relative overflow-hidden rounded-card p-5 border-l-4 border-l-signal-red">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-signal-red animate-pulse" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-signal-red">
                Breaking News Candidates
              </h3>
            </div>
            <Link
              href="/events"
              className="text-xs font-mono font-medium text-paper-400 hover:text-accent-green transition-colors flex items-center gap-1"
            >
              Feed <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-white/[0.06] pt-1">
            {breaking.data?.items.length === 0 && (
              <p className="text-xs text-paper-500 py-6 text-center font-mono">No active velocity spikes detected.</p>
            )}
            {breaking.data?.items.map((e) => (
              <Link
                key={e.id}
                href={`/events/${e.id}`}
                className="group flex items-center justify-between gap-4 py-3 hover:bg-white/[0.02] px-1 rounded transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-display text-sm font-semibold text-paper-200 group-hover:text-accent-green transition-colors">
                    {e.title}
                  </p>
                  <p className="mt-0.5 text-[11px] font-mono text-paper-500">
                    {e.article_count} sources · {relativeTime(e.last_seen_at ?? e.created_at)}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2.5">
                  <TrendScoreMeter score={e.trend_score} />
                  <span className="text-[11px] font-mono text-accent-green opacity-0 group-hover:opacity-100 transition-opacity">
                    →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Trending Events */}
        <div className="card-editorial relative overflow-hidden rounded-card p-5 border-l-4 border-l-accent-gold">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-accent-gold" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-accent-gold">
                Hottest Trending Topics
              </h3>
            </div>
            <Link
              href="/trends"
              className="text-xs font-mono font-medium text-paper-400 hover:text-accent-green transition-colors flex items-center gap-1"
            >
              Radar <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-white/[0.06] pt-1">
            {trending.data?.items.length === 0 && (
              <p className="text-xs text-paper-500 py-6 text-center font-mono">No trending spikes currently active.</p>
            )}
            {trending.data?.items.map((e) => (
              <Link
                key={e.id}
                href={`/events/${e.id}`}
                className="group flex items-center justify-between gap-4 py-3 hover:bg-white/[0.02] px-1 rounded transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-display text-sm font-semibold text-paper-200 group-hover:text-accent-green transition-colors">
                    {e.title}
                  </p>
                  <p className="mt-0.5 text-[11px] font-mono text-paper-500">
                    {e.article_count} sources · {relativeTime(e.last_seen_at ?? e.created_at)}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2.5">
                  <TrendScoreMeter score={e.trend_score} />
                  <span className="text-[11px] font-mono text-accent-green opacity-0 group-hover:opacity-100 transition-opacity">
                    →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Live Articles Stream & Source Health */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="card-editorial rounded-card p-5 lg:col-span-2">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2">
              <Newspaper className="h-4 w-4 text-paper-300" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-paper-300">
                Live Ingested Wire
              </h3>
            </div>
            <Link href="/articles" className="text-xs font-mono text-paper-400 hover:text-accent-green transition-colors">
              View stream →
            </Link>
          </div>
          <div className="divide-y divide-white/[0.06] pt-1">
            {articles.isLoading && <p className="text-xs text-paper-500 py-4 font-mono">Connecting to wire…</p>}
            {articles.data?.items.length === 0 && (
              <p className="text-xs text-paper-500 py-4 font-mono">No incoming wire traffic recorded.</p>
            )}
            {articles.data?.items.map((a) => (
              <div
                key={a.id}
                className="flex items-start justify-between gap-4 py-3 hover:bg-white/[0.015] px-1 rounded transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-paper-100 line-clamp-1 leading-snug">
                    {a.title ?? "(untitled)"}
                  </p>
                  <div className="mt-1 flex items-center gap-2 text-[11px] font-mono text-paper-500">
                    <span>{relativeTime(a.published_at ?? a.created_at)}</span>
                    {a.categories[0] && (
                      <>
                        <span>·</span>
                        <span className="text-paper-400">{a.categories[0]}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <RelevanceMeter score={a.ethiopia_relevance_score} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Source Health Desk */}
        <div className="card-editorial rounded-card p-5">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-paper-300" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-paper-300">
                Source Network Health
              </h3>
            </div>
            <Link href="/sources" className="text-xs font-mono text-paper-400 hover:text-accent-green transition-colors">
              All sources →
            </Link>
          </div>
          <div className="divide-y divide-white/[0.06] pt-1">
            {(health.data ?? []).slice(0, 8).map((h) => (
              <div key={h.id} className="flex items-center justify-between gap-2 py-2.5">
                <span className="truncate text-xs font-medium text-paper-200">{h.name}</span>
                <HealthDot status={h.health_status} />
              </div>
            ))}
            {health.isError && (
              <p className="text-xs text-signal-red py-2 font-mono">Service telemetry unavailable.</p>
            )}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3 text-xs text-paper-500">
          <Badge variant="green">RSS ingestion ✓</Badge>
          <Badge variant="green">Relevance ✓</Badge>
          <Badge variant="green">Analysis ✓</Badge>
          <Badge variant="green">Embeddings ✓</Badge>
          <Badge variant="green">Event clustering ✓</Badge>
          <Badge variant="green">Verification ✓</Badge>
          <Badge variant="green">Trend intelligence ✓</Badge>
          <Badge variant="muted">Telegram · Phase 1.5</Badge>
          <Badge variant="muted">Instagram publish · Phase 5</Badge>
        </CardContent>
      </Card>
    </div>
  );
}
