"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle,
  ExternalLink,
  Image as ImageIcon,
  Palette,
  Sparkles,
} from "lucide-react";
import { api, postsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
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
  const queryClient = useQueryClient();
  const [showClearModal, setShowClearModal] = useState(false);
  const [clearReason, setClearReason] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: e, isLoading, isError } = useQuery({
    queryKey: ["event", id],
    queryFn: () => api.getEvent(id),
  });

  const clearMutation = useMutation({
    mutationFn: () => api.clearReview(id, clearReason),
    onSuccess: () => {
      setShowClearModal(false);
      setClearReason("");
      setFeedback("Editorial review cleared. Event is now auto-publish eligible.");
      void queryClient.invalidateQueries({ queryKey: ["event", id] });
    },
    onError: (err: Error) => setFeedback(`Failed to clear review: ${err.message}`),
  });

  const composeMutation = useMutation({
    mutationFn: () => postsApi.compose({ event_id: id, format: "portrait" }),
    onSuccess: (res) => {
      setFeedback(`Instagram post composition enqueued (Task: ${res.task_id.slice(0, 8)}). View in Posts.`);
      void queryClient.invalidateQueries({ queryKey: ["posts"] });
    },
    onError: (err: Error) => setFeedback(`Failed to enqueue compose: ${err.message}`),
  });

  const generateVisualMutation = useMutation({
    mutationFn: () => postsApi.generateAsset(id),
    onSuccess: (res) => {
      setFeedback(`Visual asset generation enqueued (Task: ${res.task_id.slice(0, 8)}).`);
    },
    onError: (err: Error) => setFeedback(`Failed to generate visual: ${err.message}`),
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

      {/* Feedback Toast */}
      {feedback && (
        <div className="flex items-center justify-between rounded-card border border-accent-green/40 bg-accent-green/10 px-4 py-2.5 text-sm text-accent-green">
          <span>{feedback}</span>
          <button
            onClick={() => setFeedback(null)}
            className="text-xs uppercase hover:underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Editorial Intelligence & Publishing Actions */}
      <Card className="border-accent-green/30 bg-ink-850">
        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase font-mono tracking-label text-accent-green">
                Editorial Control Desk
              </span>
              {e.auto_publish_eligible ? (
                <Badge variant="green">Auto-Publish Ready</Badge>
              ) : e.review_required ? (
                <Badge variant="gold">Human Clearance Required</Badge>
              ) : (
                <Badge variant="muted">Restricted</Badge>
              )}
            </div>
            <p className="text-xs text-paper-400">
              Transform verified claims into Instagram posts, generate cinematic visuals, or clear review blocks.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {e.review_required && (
              <Button
                variant="outline"
                size="sm"
                className="border-accent-gold text-accent-gold hover:bg-accent-gold/10"
                onClick={() => setShowClearModal(true)}
              >
                <CheckCircle className="h-3.5 w-3.5" /> Clear Review Block
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              disabled={generateVisualMutation.isPending}
              onClick={() => generateVisualMutation.mutate()}
            >
              <ImageIcon className="h-3.5 w-3.5" />
              {generateVisualMutation.isPending ? "Generating…" : "Generate Visual"}
            </Button>

            <Button
              size="sm"
              disabled={composeMutation.isPending}
              onClick={() => composeMutation.mutate()}
            >
              <Sparkles className="h-3.5 w-3.5" />
              {composeMutation.isPending ? "Queuing…" : "Compose Instagram Post"}
            </Button>

            <Link href={`/studio/templates?event_id=${e.id}`}>
              <Button variant="ghost" size="sm">
                <Palette className="h-3.5 w-3.5" /> Open in Studio
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Clear Review Dialog Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <Card className="w-full max-w-md border-ink-600 bg-ink-900 p-6 space-y-4">
            <h3 className="font-display text-lg font-semibold text-paper-50">
              Clear Editorial Review
            </h3>
            <p className="text-xs text-paper-300">
              Clearing review marks this event as human-cleared and enables automated Instagram post publishing. Provide the editorial justification for the audit trail.
            </p>
            <textarea
              className="w-full h-24 rounded-card border border-ink-700 bg-ink-800 p-3 text-sm text-paper-100 placeholder:text-paper-600 focus:outline-none focus:border-accent-green"
              placeholder="e.g. Verified against official government press release and 3 wire reports."
              value={clearReason}
              onChange={(e) => setClearReason(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowClearModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!clearReason.trim() || clearMutation.isPending}
                onClick={() => clearMutation.mutate()}
              >
                {clearMutation.isPending ? "Clearing…" : "Confirm Clearance"}
              </Button>
            </div>
          </Card>
        </div>
      )}

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
