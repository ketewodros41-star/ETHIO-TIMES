"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
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

  const { data, isLoading } = useQuery({
    queryKey: ["articles", search, page],
    queryFn: () =>
      api.listArticles({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
      }),
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
        <span className="text-xs text-paper-500">{total} articles</span>
      </div>

      {isLoading && <p className="text-sm text-paper-500">Loading…</p>}
      {!isLoading && items.length === 0 && (
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
