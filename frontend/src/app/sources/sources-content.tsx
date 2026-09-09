"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Play } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { HealthDot, VerificationBadge } from "@/components/status";
import { relativeTime } from "@/lib/utils";
import type { Source } from "@/lib/types";

export function SourcesContent() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["sources", search],
    queryFn: () => api.listSources({ limit: 200, search: search || undefined }),
  });

  const ingestAll = useMutation({
    mutationFn: () => api.triggerIngest(),
    onSuccess: (res) => flash(res.message),
    onError: (e: Error) => flash(e.message),
  });

  const ingestOne = useMutation({
    mutationFn: (id: string) => api.triggerIngest(id),
    onSuccess: (res) => flash(res.message),
    onError: (e: Error) => flash(e.message),
  });

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
    void qc.invalidateQueries({ queryKey: ["source-health"] });
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Input
          placeholder="Search sources…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["sources"] })}
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => ingestAll.mutate()}
            disabled={ingestAll.isPending}
          >
            <Play className="h-4 w-4" />
            {ingestAll.isPending ? "Enqueuing…" : "Ingest all active"}
          </Button>
        </div>
      </div>

      {toast && (
        <div className="rounded-card border border-accent-green/40 bg-accent-green/10 px-4 py-2 text-sm text-accent-green">
          {toast}
        </div>
      )}

      <Card>
        <Table>
          <THead>
            <TR>
              <TH>Source</TH>
              <TH>Type</TH>
              <TH>Ingest</TH>
              <TH>Verification</TH>
              <TH>Health</TH>
              <TH>Last check</TH>
              <TH>Articles</TH>
              <TH className="text-right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {isLoading && (
              <TR>
                <TD colSpan={8} className="text-paper-500">
                  Loading…
                </TD>
              </TR>
            )}
            {items.map((s: Source) => (
              <TR key={s.id}>
                <TD>
                  <div className="flex flex-col">
                    <span className="text-paper-50">{s.name}</span>
                    <span className="font-mono text-[11px] text-paper-500">{s.slug}</span>
                  </div>
                </TD>
                <TD>
                  <span className="text-xs text-paper-300">
                    {s.source_type.replace(/_/g, " ")}
                  </span>
                </TD>
                <TD>
                  {s.rss_url ? (
                    <Badge variant="green">RSS</Badge>
                  ) : s.source_type === "telegram_channel" ? (
                    <Badge variant="gold">Telegram</Badge>
                  ) : (
                    <Badge variant="muted">crawler</Badge>
                  )}
                </TD>
                <TD>
                  <VerificationBadge status={s.verification_status} />
                </TD>
                <TD>
                  <HealthDot status={s.health_status} />
                </TD>
                <TD className="text-xs text-paper-500">
                  {relativeTime(s.last_checked_at)}
                </TD>
                <TD className="font-mono text-xs tabular-nums text-paper-300">
                  {s.total_articles_ingested}
                </TD>
                <TD className="text-right">
                  <Button
                    variant="subtle"
                    size="sm"
                    disabled={!s.is_active || ingestOne.isPending}
                    onClick={() => ingestOne.mutate(s.id)}
                  >
                    Ingest
                  </Button>
                </TD>
              </TR>
            ))}
            {!isLoading && items.length === 0 && (
              <TR>
                <TD colSpan={8} className="text-paper-500">
                  No sources found.
                </TD>
              </TR>
            )}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
