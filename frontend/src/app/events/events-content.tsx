"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Layers, Users } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EventStatusBadge } from "@/components/status";
import { relativeTime } from "@/lib/utils";

const PAGE_SIZE = 25;

export function EventsContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["events", search, page],
    queryFn: () =>
      api.listEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
      }),
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Input
          placeholder="Search events…"
          value={search}
          onChange={(e) => {
            setPage(0);
            setSearch(e.target.value);
          }}
          className="max-w-sm"
        />
        <span className="text-xs text-paper-500">{total} clustered events</span>
      </div>

      {isLoading && <p className="text-sm text-paper-500">Loading…</p>}
      {!isLoading && items.length === 0 && (
        <Card className="p-8 text-center text-sm text-paper-500">
          No events yet. Ingest sources and run the intelligence pipeline to
          cluster articles into events.
        </Card>
      )}

      <div className="space-y-3">
        {items.map((e) => (
          <Link key={e.id} href={`/events/${e.id}`}>
            <Card className="p-4 transition-colors hover:border-ink-600">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <EventStatusBadge status={e.status} />
                    {e.primary_category && (
                      <Badge variant="default">{e.primary_category}</Badge>
                    )}
                    {e.primary_region && (
                      <Badge variant="muted">{e.primary_region}</Badge>
                    )}
                  </div>
                  <h3 className="font-display text-lg font-medium leading-snug text-paper-50">
                    {e.title}
                  </h3>
                  {e.summary && (
                    <p className="mt-1 line-clamp-2 text-sm text-paper-300">
                      {e.summary}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-500">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="h-3 w-3" /> {e.article_count} articles
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3 w-3" /> {e.source_count} sources
                    </span>
                    <span>updated {relativeTime(e.last_seen_at)}</span>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-mono text-xs text-paper-500">confidence</div>
                  <div className="font-display text-2xl tabular-nums text-paper-50">
                    {Math.round(e.cluster_confidence * 100)}
                  </div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
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
