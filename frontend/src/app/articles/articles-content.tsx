"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ExternalLink, Radio, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ProcessingBadge,
  RelevanceBadge,
  RelevanceMeter,
} from "@/components/status";
import { formatDate } from "@/lib/utils";

const PAGE_SIZE = 25;

export function ArticlesContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const { data: sourcesData } = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.listSources({ limit: 200 }),
    staleTime: 60000,
  });

  const sourceMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of sourcesData?.items ?? []) {
      map.set(s.id, s.name);
    }
    return map;
  }, [sourcesData]);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["articles", search, page],
    queryFn: () =>
      api.listArticles({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
      }),
    refetchInterval: 120_000,
    refetchIntervalInBackground: false,
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;
  const maxPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Input
          placeholder="Search headlines…"
          value={search}
          onChange={(e) => {
            setPage(0);
            setSearch(e.target.value);
          }}
          className="max-w-sm"
        />
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono text-paper-400 bg-ink-850 border border-ink-700 px-2.5 py-1 rounded-full">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-green animate-pulse" />
            Live Sync: 2m
          </span>
          <span className="text-xs text-paper-500">{total} articles</span>
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
              <span>Failed to load articles: {error instanceof Error ? error.message : "Unknown error"}</span>
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
          <span>Loading articles…</span>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <Card className="p-8 text-center text-sm text-paper-500">
          No articles yet. Trigger ingestion from the Sources page.
        </Card>
      )}

      <div className="space-y-3">
        {items.map((a) => (
          <Card key={a.id} className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  {a.categories.slice(0, 2).map((c) => (
                    <Badge key={c} variant="default">
                      {c}
                    </Badge>
                  ))}
                  <ProcessingBadge status={a.processing_status} />
                  <RelevanceBadge
                    decision={a.relevance_decision}
                    score={a.relevance_score}
                  />
                  {a.detected_language && (
                    <Badge variant="muted">{a.detected_language}</Badge>
                  )}
                </div>
                <h3 className="font-display text-lg font-medium leading-snug text-paper-50">
                  {a.title ?? "(untitled)"}
                </h3>
                {a.summary && (
                  <p className="mt-1 line-clamp-2 text-sm text-paper-300">{a.summary}</p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-500">
                  {a.source_id && (
                    <Link
                      href={`/sources/${a.source_id}`}
                      className="inline-flex items-center gap-1.5 text-accent-gold hover:text-paper-100 hover:underline font-medium transition-colors"
                      title="View all news from this publisher"
                    >
                      <Radio className="h-3 w-3 text-accent-gold" />
                      <span>{sourceMap.get(a.source_id) ?? "Publisher"}</span>
                    </Link>
                  )}
                  <span>{formatDate(a.published_at ?? a.created_at)}</span>
                  {a.author && <span>· {a.author}</span>}
                  {a.url && (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-accent-green hover:underline"
                    >
                      source <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
              <div className="shrink-0 pt-1">
                <RelevanceMeter score={a.ethiopia_relevance_score} />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <span className="text-xs text-paper-500">
            Page {page + 1} of {maxPage + 1}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= maxPage}
            onClick={() => setPage((p) => Math.min(maxPage, p + 1))}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
