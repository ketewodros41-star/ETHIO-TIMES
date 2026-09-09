"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HealthDot, RelevanceMeter } from "@/components/status";
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

  const srcItems = sources.data?.items ?? [];
  const activeCount = srcItems.filter((s) => s.is_active).length;
  const needsVerify = srcItems.filter(
    (s) => s.verification_status === "needs_verification",
  ).length;
  const healthy = (health.data ?? []).filter((h) => h.health_status === "healthy").length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat
          label="Sources"
          value={sources.data?.meta.total ?? "—"}
          hint={`${activeCount} active`}
        />
        <Stat label="Articles ingested" value={articles.data?.meta.total ?? "—"} />
        <Stat label="Healthy sources" value={health.data ? healthy : "—"} />
        <Stat
          label="Needs verification"
          value={needsVerify}
          hint="Telegram / unconfirmed"
        />
      </div>

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
          <Badge variant="muted">Website crawler · Phase 2</Badge>
          <Badge variant="muted">Telegram · Phase 1.5</Badge>
          <Badge variant="muted">Event clustering · Phase 2</Badge>
          <Badge variant="muted">Verification · Phase 3</Badge>
          <Badge variant="muted">Visual Director · Phase 3</Badge>
          <Badge variant="muted">Instagram publish · Phase 4</Badge>
        </CardContent>
      </Card>
    </div>
  );
}
