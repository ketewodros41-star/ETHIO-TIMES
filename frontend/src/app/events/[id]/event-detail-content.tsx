"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ContradictionSeverityBadge,
  EventStatusBadge,
  EventVerificationBadge,
  ProcessingBadge,
  RelationBadge,
  TrendScoreMeter,
  TrendStatusBadge,
  VerificationScoreMeter,
} from "@/components/status";
import { formatDate } from "@/lib/utils";

const TIMELINE_LABEL: Record<string, string> = {
  first_report: "First report",
  source_confirmation: "Source confirmation",
  new_development: "New development",
  correction: "Correction",
};

export function EventDetailContent({ id }: { id: string }) {
  const { data: e, isLoading, isError } = useQuery({
    queryKey: ["event", id],
    queryFn: () => api.getEvent(id),
  });

  if (isLoading) return <p className="text-sm text-paper-500">Loading…</p>;
  if (isError || !e)
    return <p className="text-sm text-signal-red">Event not found.</p>;

  const explanation = e.verification_explanation ?? {};
  const components =
    (explanation.components as Record<string, { score?: number; detail?: unknown }> | undefined) ??
    {};

  return (
    <div className="space-y-6">
      <Link
        href="/events"
        className="inline-flex items-center gap-1 text-xs text-paper-500 hover:text-paper-300"
      >
        <ArrowLeft className="h-3 w-3" /> Back to events
      </Link>

      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <TrendStatusBadge status={e.trend_status} />
          {e.breaking_candidate && <Badge variant="red">breaking candidate</Badge>}
          <EventVerificationBadge status={e.event_verification_status} />
          <EventStatusBadge status={e.status} />
          {e.review_required && <Badge variant="gold">review required</Badge>}
          {e.primary_source_available && (
            <Badge variant="green">primary source available</Badge>
          )}
          {!e.auto_publish_eligible && (
            <Badge variant="muted">auto-publish off</Badge>
          )}
          {e.primary_category && <Badge variant="default">{e.primary_category}</Badge>}
          {e.primary_region && <Badge variant="muted">{e.primary_region}</Badge>}
        </div>
        <h1 className="font-display text-2xl font-semibold leading-tight text-paper-50">
          {e.title}
        </h1>
        {e.summary && <p className="mt-2 max-w-3xl text-sm text-paper-300">{e.summary}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat label="Trend" value={Math.round(e.trend_score)} />
        <Stat label="Verification" value={e.verification_score} />
        <Stat label="Articles" value={e.article_count} />
        <Stat label="Sources" value={e.source_count} />
        <Stat label="Claims" value={e.claims.length} />
        <Stat label="Contradictions" value={e.contradictions.length} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Trend intelligence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <TrendStatusBadge status={e.trend_status} />
            <TrendScoreMeter score={e.trend_score} />
            <span className="text-xs text-paper-500">
              editorial importance {Math.round(e.editorial_importance)}
              {e.trend_scored_at ? ` · scored ${formatDate(e.trend_scored_at)}` : ""}
            </span>
          </div>
          {(() => {
            const breakdown = e.trend_breakdown ?? {};
            const trendComponents =
              (breakdown.components as
                | Record<string, { score?: number; weight?: number; detail?: unknown }>
                | undefined) ?? {};
            const reasons = (breakdown.breaking_reasons as string[] | undefined) ?? [];
            return (
              <>
                {reasons.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {reasons.map((r) => (
                      <Badge key={r} variant="red">
                        {r.replaceAll("_", " ")}
                      </Badge>
                    ))}
                  </div>
                )}
                {Object.keys(trendComponents).length > 0 && (
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    {Object.entries(trendComponents).map(([key, val]) => (
                      <div key={key} className="rounded-card border border-ink-800 p-3">
                        <p className="text-[11px] uppercase tracking-label text-paper-500">
                          {key.replaceAll("_", " ")}
                        </p>
                        <p className="mt-1 font-mono text-lg tabular-nums text-paper-50">
                          {typeof val.score === "number" ? Math.round(val.score) : "—"}
                        </p>
                        <p className="text-[11px] text-paper-500">
                          weight {typeof val.weight === "number" ? Math.round(val.weight * 100) : "—"}%
                        </p>
                        <div className="mt-2 h-1 overflow-hidden rounded-full bg-ink-700">
                          <div
                            className="h-full bg-accent-green"
                            style={{
                              width: `${Math.max(0, Math.min(100, Number(val.score) || 0))}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            );
          })()}
          {e.velocity_metrics.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-label text-paper-500">
                Velocity windows
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-paper-500">
                    <tr>
                      <th className="pb-2 font-medium">Window</th>
                      <th className="pb-2 font-medium">Articles</th>
                      <th className="pb-2 font-medium">Sources</th>
                      <th className="pb-2 font-medium">Per hour</th>
                      <th className="pb-2 font-medium">Growth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {e.velocity_metrics.map((row) => (
                      <tr key={row.window_hours} className="border-t border-ink-800">
                        <td className="py-2 text-paper-300">{row.window_hours}h</td>
                        <td className="py-2 font-mono tabular-nums">{row.article_count}</td>
                        <td className="py-2 font-mono tabular-nums">
                          {row.unique_source_count}
                        </td>
                        <td className="py-2 font-mono tabular-nums">
                          {row.articles_per_hour.toFixed(2)}
                        </td>
                        <td className="py-2 font-mono tabular-nums">
                          {row.growth_rate.toFixed(2)}×
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <EventVerificationBadge status={e.event_verification_status} />
            <VerificationScoreMeter score={e.verification_score} />
            <span className="text-xs text-paper-500">
              processing {e.verification_processing_status.replaceAll("_", " ")}
              {e.verified_at ? ` · verified ${formatDate(e.verified_at)}` : ""}
            </span>
          </div>
          {e.review_reasons.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-label text-paper-500">
                Review reasons
              </p>
              <div className="flex flex-wrap gap-2">
                {e.review_reasons.map((r) => (
                  <Badge key={r} variant="gold">
                    {r}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {e.cited_institutions.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-label text-paper-500">
                Cited institutions
              </p>
              <div className="flex flex-wrap gap-2">
                {e.cited_institutions.map((n) => (
                  <Badge key={n} variant="default">
                    {n}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {Object.keys(components).length > 0 && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              {Object.entries(components).map(([key, val]) => (
                <div key={key} className="rounded-card border border-ink-800 p-3">
                  <p className="text-[11px] uppercase tracking-label text-paper-500">
                    {key.replaceAll("_", " ")}
                  </p>
                  <p className="mt-1 font-mono text-lg tabular-nums text-paper-50">
                    {typeof val.score === "number" ? Math.round(val.score) : "—"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Claims ({e.claims.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {e.claims.length === 0 && (
                <p className="text-sm text-paper-500">
                  No evidenced claims yet. Verification runs after clustering.
                </p>
              )}
              {e.claims.map((claim) => (
                <div
                  key={claim.id}
                  className="border-b border-ink-800 pb-3 last:border-0"
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge variant="default">{claim.claim_type}</Badge>
                    {claim.is_major && <Badge variant="muted">major</Badge>}
                    {claim.normalized_value && (
                      <span className="font-mono text-xs text-accent-green">
                        {claim.normalized_value}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-paper-50">{claim.claim_text}</p>
                  <div className="mt-2 space-y-1">
                    {claim.evidence.map((ev) => (
                      <p key={`${claim.id}-${ev.article_id}`} className="text-xs text-paper-500">
                        “{ev.excerpt}”
                        {ev.url && (
                          <>
                            {" "}
                            <a
                              href={ev.url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-accent-green hover:underline"
                            >
                              source <ExternalLink className="h-3 w-3" />
                            </a>
                          </>
                        )}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Grouped coverage ({e.articles.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {e.articles.map((link) => (
                <div
                  key={link.article.id}
                  className="flex items-start justify-between gap-4 border-b border-ink-800 pb-3 last:border-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <RelationBadge relation={link.relation_type} />
                      {link.article.source && (
                        <span className="text-xs text-paper-500">
                          {link.article.source.name}
                        </span>
                      )}
                      {link.article.detected_language && (
                        <Badge variant="muted">{link.article.detected_language}</Badge>
                      )}
                    </div>
                    <p className="text-sm text-paper-50">
                      {link.article.title ?? "(untitled)"}
                    </p>
                    <div className="mt-1 flex items-center gap-3 text-xs text-paper-500">
                      <span>{formatDate(link.article.published_at)}</span>
                      <span>similarity {Math.round(link.similarity_score * 100)}</span>
                      <ProcessingBadge status={link.article.processing_status} />
                      {link.article.url && (
                        <a
                          href={link.article.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-accent-green hover:underline"
                        >
                          source <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Contradictions ({e.contradictions.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {e.contradictions.length === 0 && (
                <p className="text-sm text-paper-500">None detected across sources.</p>
              )}
              {e.contradictions.map((c) => (
                <div key={c.id} className="space-y-1">
                  <ContradictionSeverityBadge severity={c.severity} />
                  <p className="text-sm text-paper-300">{c.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {e.timeline.map((t) => (
                <div key={t.id} className="flex gap-3">
                  <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent-green" />
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-label text-paper-500">
                      {TIMELINE_LABEL[t.entry_type] ?? t.entry_type}
                    </p>
                    <p className="truncate text-sm text-paper-300">
                      {t.title ?? "—"}
                    </p>
                    <p className="text-xs text-paper-500">{formatDate(t.occurred_at)}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {e.key_entities.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Key entities</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {e.key_entities.slice(0, 24).map((k) => (
                  <Badge key={k} variant="default">
                    {k}
                  </Badge>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-[11px] uppercase tracking-label text-paper-500">{label}</p>
        <p className="mt-1 font-display text-3xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}
