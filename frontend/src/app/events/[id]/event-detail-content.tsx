"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  EventStatusBadge,
  ProcessingBadge,
  RelationBadge,
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
          <EventStatusBadge status={e.status} />
          {e.primary_category && <Badge variant="default">{e.primary_category}</Badge>}
          {e.primary_region && <Badge variant="muted">{e.primary_region}</Badge>}
        </div>
        <h1 className="font-display text-2xl font-semibold leading-tight text-paper-50">
          {e.title}
        </h1>
        {e.summary && <p className="mt-2 max-w-3xl text-sm text-paper-300">{e.summary}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Articles" value={e.article_count} />
        <Stat label="Sources" value={e.source_count} />
        <Stat label="Cluster confidence" value={`${Math.round(e.cluster_confidence * 100)}`} />
        <Stat label="Significance" value={`${Math.round(e.significance_score)}`} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
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

        <div className="space-y-6">
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
