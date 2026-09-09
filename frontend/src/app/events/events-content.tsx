"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Layers, ShieldAlert, Users } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  EventStatusBadge,
  EventVerificationBadge,
  VerificationScoreMeter,
} from "@/components/status";
import { relativeTime } from "@/lib/utils";
import type { EventVerificationStatus } from "@/lib/types";

const PAGE_SIZE = 25;

const VERIFY_FILTERS: { value: EventVerificationStatus | ""; label: string }[] = [
  { value: "", label: "All verification" },
  { value: "unverified", label: "Unverified" },
  { value: "developing", label: "Developing" },
  { value: "partially_confirmed", label: "Partially confirmed" },
  { value: "confirmed", label: "Confirmed" },
  { value: "contradicted", label: "Contradicted" },
];

export function EventsContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [verification, setVerification] = useState<EventVerificationStatus | "">("");
  const [reviewOnly, setReviewOnly] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["events", search, page, verification, reviewOnly],
    queryFn: () =>
      api.listEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
        verification_status: verification || undefined,
        review_required: reviewOnly ? true : undefined,
      }),
  });

  const items = data?.items ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Search events…"
            value={search}
            onChange={(e) => {
              setPage(0);
              setSearch(e.target.value);
            }}
            className="max-w-sm"
          />
          <select
            value={verification}
            onChange={(e) => {
              setPage(0);
              setVerification(e.target.value as EventVerificationStatus | "");
            }}
            className="h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-xs text-paper-300"
          >
            {VERIFY_FILTERS.map((opt) => (
              <option key={opt.label} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-2 text-xs text-paper-300">
            <input
              type="checkbox"
              checked={reviewOnly}
              onChange={(e) => {
                setPage(0);
                setReviewOnly(e.target.checked);
              }}
            />
            Review required
          </label>
        </div>
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
                    <EventVerificationBadge status={e.event_verification_status} />
                    <EventStatusBadge status={e.status} />
                    {e.review_required && (
                      <Badge variant="gold">review required</Badge>
                    )}
                    {e.primary_source_available && (
                      <Badge variant="green">primary source</Badge>
                    )}
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
                    {e.review_required && (
                      <span className="inline-flex items-center gap-1 text-accent-gold">
                        <ShieldAlert className="h-3 w-3" /> human review
                      </span>
                    )}
                    <span>updated {relativeTime(e.last_seen_at)}</span>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-mono text-xs text-paper-500">verification</div>
                  <div className="font-display text-2xl tabular-nums text-paper-50">
                    {e.verification_score}
                  </div>
                  <div className="mt-1 flex justify-end">
                    <VerificationScoreMeter score={e.verification_score} />
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
