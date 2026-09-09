"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EventStatusBadge, EventVerificationBadge, HealthDot, RelevanceMeter, TrendStatusBadge } from "@/components/status";
import { relativeTime } from "@/lib/utils";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-[11px] uppercase tracking-label text-paper-500">{label}</p>
        <p className="mt-2 font-display text-4xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="mt-1 text-xs text-paper-500">{hint}</p>}
      </CardContent>
    </Card>
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

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat
          label="Sources"
          value={sources.data?.meta.total ?? "—"}
          hint={`${activeCount} active · ${healthy} healthy`}
        />
        <Stat
          label="Articles"
          value={stats.data?.total_articles ?? articles.data?.meta.total ?? "—"}
          hint={stats.data ? `${stats.data.embedded} embedded` : undefined}
        />
        <Stat
          label="Events clustered"
          value={stats.data?.total_events ?? "—"}
          hint={`${clustered} articles processed`}
        />
        <Stat
          label="Ethiopia-relevant"
          value={stats.data?.ethiopia_related ?? "—"}
          hint="passed relevance filter"
        />
        <Stat
          label="Needs review"
          value={stats.data?.review_required_events ?? "—"}
          hint="sensitive or contradicted"
        />
        <Stat
          label="Breaking"
          value={stats.data?.breaking_candidates ?? "—"}
          hint="velocity burst candidates"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Breaking</CardTitle>
            <Link
              href="/events"
              className="text-xs text-accent-green hover:underline"
            >
              Event feed →
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {breaking.data?.items.length === 0 && (
              <p className="text-sm text-paper-500">No breaking candidates yet.</p>
            )}
            {breaking.data?.items.map((e) => (
              <Link
                key={e.id}
                href={`/events/${e.id}`}
                className="flex items-center justify-between gap-4 border-b border-ink-800 py-2 last:border-0 hover:text-paper-50"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-paper-300">
                  {e.title}
                </span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-paper-500">
                  <span className="font-mono tabular-nums">{Math.round(e.trend_score)}</span>
                  <TrendStatusBadge status={e.trend_status} />
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Trending</CardTitle>
            <Link
              href="/events"
              className="text-xs text-accent-green hover:underline"
            >
              Event feed →
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {trending.data?.items.length === 0 && (
              <p className="text-sm text-paper-500">No trending events yet.</p>
            )}
            {trending.data?.items.map((e) => (
              <Link
                key={e.id}
                href={`/events/${e.id}`}
                className="flex items-center justify-between gap-4 border-b border-ink-800 py-2 last:border-0 hover:text-paper-50"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-paper-300">
                  {e.title}
                </span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-paper-500">
                  <span className="font-mono tabular-nums">{Math.round(e.trend_score)}</span>
                  <TrendStatusBadge status={e.trend_status} />
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Developing events</CardTitle>
          <Link href="/events" className="text-xs text-accent-green hover:underline">
            View all →
          </Link>
        </CardHeader>
        <CardContent className="space-y-2">
          {events.data?.items.length === 0 && (
            <p className="text-sm text-paper-500">
              No events yet. Run the intelligence pipeline to cluster articles.
            </p>
          )}
          {events.data?.items.map((e) => (
            <Link
              key={e.id}
              href={`/events/${e.id}`}
              className="flex items-center justify-between gap-4 border-b border-ink-800 py-2 last:border-0 hover:text-paper-50"
            >
              <span className="min-w-0 flex-1 truncate text-sm text-paper-300">
                {e.title}
              </span>
              <span className="flex shrink-0 items-center gap-3 text-xs text-paper-500">
                <span>{e.article_count} arts · {e.source_count} src</span>
                <EventVerificationBadge status={e.event_verification_status} />
                <TrendStatusBadge status={e.trend_status} />
                <EventStatusBadge status={e.status} />
              </span>
            </Link>
          ))}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Latest articles</CardTitle>
            <Link href="/articles" className="text-xs text-accent-green hover:underline">
              View all →
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {articles.isLoading && <p className="text-sm text-paper-500">Loading…</p>}
            {articles.data?.items.length === 0 && (
              <p className="text-sm text-paper-500">
                No articles yet. Trigger ingestion from the Sources page.
              </p>
            )}
            {articles.data?.items.map((a) => (
              <div
                key={a.id}
                className="flex items-start justify-between gap-4 border-b border-ink-800 pb-3 last:border-0"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm text-paper-50">{a.title ?? "(untitled)"}</p>
                  <p className="mt-1 text-xs text-paper-500">
                    {relativeTime(a.published_at ?? a.created_at)}
                    {a.categories[0] ? ` · ${a.categories[0]}` : ""}
                  </p>
                </div>
                <RelevanceMeter score={a.ethiopia_relevance_score} />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Source health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(health.data ?? []).slice(0, 10).map((h) => (
              <div key={h.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-sm text-paper-300">{h.name}</span>
                <HealthDot status={h.health_status} />
              </div>
            ))}
            {health.isError && (
              <p className="text-sm text-signal-red">Could not load health.</p>
            )}
          </CardContent>
        </Card>
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
