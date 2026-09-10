"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Play, Plus, Check, ExternalLink } from "lucide-react";
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
  const [ingestingId, setIngestingId] = useState<string | null>(null);
  const [ingestedMap, setIngestedMap] = useState<Record<string, number>>({});

  // Add Source Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newWebsite, setNewWebsite] = useState("");
  const [newRssUrl, setNewRssUrl] = useState("");
  const [newType, setNewType] = useState("rss_feed");
  const [newFreq, setNewFreq] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: ["sources", search],
    queryFn: () => api.listSources({ limit: 200, search: search || undefined }),
    refetchInterval: 120_000,
    refetchIntervalInBackground: false,
  });

  function refreshAll() {
    void qc.invalidateQueries({ queryKey: ["sources"] });
    void qc.invalidateQueries({ queryKey: ["source-health"] });
    void qc.invalidateQueries({ queryKey: ["articles"] });
    void qc.invalidateQueries({ queryKey: ["events"] });
    void qc.invalidateQueries({ queryKey: ["pipeline-stats"] });
  }

  function scheduleSync() {
    refreshAll();
    setTimeout(refreshAll, 1500);
    setTimeout(refreshAll, 4000);
    setTimeout(refreshAll, 8000);
    setTimeout(refreshAll, 15000);
  }

  const ingestAll = useMutation({
    mutationFn: () => api.triggerIngest(),
    onMutate: () => setIngestingId("all"),
    onSettled: () => setIngestingId(null),
    onSuccess: (res) => {
      flash(res.message);
      scheduleSync();
    },
    onError: (e: Error) => flash(e.message),
  });

  const ingestOne = useMutation({
    mutationFn: (id: string) => api.triggerIngest(id),
    onMutate: (id) => setIngestingId(id),
    onSettled: () => setIngestingId(null),
    onSuccess: (res, id) => {
      flash(res.message);
      setIngestedMap((prev) => ({ ...prev, [id]: Date.now() }));
      scheduleSync();
    },
    onError: (e: Error) => flash(e.message),
  });

  const createSource = useMutation({
    mutationFn: () =>
      api.createSource({
        name: newName.trim(),
        website: newWebsite.trim() || undefined,
        rss_url: newRssUrl.trim() || undefined,
        source_type: newType,
        crawl_frequency_minutes: Number(newFreq) || 30,
        is_active: true,
      }),
    onSuccess: (src) => {
      setShowAddModal(false);
      setNewName("");
      setNewWebsite("");
      setNewRssUrl("");
      flash(`Source "${src.name}" added successfully.`);
      void qc.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (e: Error) => flash(`Failed to add source: ${e.message}`),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateSource(id, { is_active }),
    onSuccess: (src) => {
      flash(`Source "${src.name}" ${src.is_active ? "activated" : "paused"}.`);
      void qc.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (e: Error) => flash(`Failed to update status: ${e.message}`),
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
          <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono text-paper-400 bg-ink-850 border border-ink-700 px-2.5 py-1 rounded-full mr-1">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-green animate-pulse" />
            Live Sync: 2m
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["sources"] })}
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddModal(true)}
          >
            <Plus className="h-4 w-4" /> Add Source
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

      {/* Add Source Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <Card className="w-full max-w-lg border-ink-600 bg-ink-900 p-6 space-y-4">
            <div>
              <h3 className="font-display text-lg font-semibold text-paper-50">
                Add Ethiopian News Source
              </h3>
              <p className="text-xs text-paper-400 mt-1">
                Configure an official Ethiopian publisher, wire, RSS feed, or telegram news channel.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs uppercase font-mono tracking-label text-paper-400 mb-1">
                  Source Name *
                </label>
                <Input
                  placeholder="e.g. Tikvah Ethiopia, Addis Standard, Capital Ethiopia"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs uppercase font-mono tracking-label text-paper-400 mb-1">
                    Source Type
                  </label>
                  <select
                    className="w-full h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-50 focus:outline-none focus:border-accent-green"
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                  >
                    <option value="rss_feed">RSS Feed</option>
                    <option value="news_site">News Site</option>
                    <option value="telegram_channel">Telegram Channel</option>
                    <option value="government_portal">Government Portal</option>
                    <option value="fact_checker">Fact Checker</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs uppercase font-mono tracking-label text-paper-400 mb-1">
                    Crawl Frequency (min)
                  </label>
                  <Input
                    type="number"
                    value={newFreq}
                    onChange={(e) => setNewFreq(Number(e.target.value))}
                    min={5}
                    max={1440}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs uppercase font-mono tracking-label text-paper-400 mb-1">
                  Website URL
                </label>
                <Input
                  placeholder="https://addisstandard.com"
                  value={newWebsite}
                  onChange={(e) => setNewWebsite(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-mono tracking-label text-paper-400 mb-1">
                  RSS Feed URL (optional)
                </label>
                <Input
                  placeholder="https://addisstandard.com/feed"
                  value={newRssUrl}
                  onChange={(e) => setNewRssUrl(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!newName.trim() || createSource.isPending}
                onClick={() => createSource.mutate()}
              >
                {createSource.isPending ? "Adding…" : "Add Source"}
              </Button>
            </div>
          </Card>
        </div>
      )}

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
              <TH>Status</TH>
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
                <TD colSpan={9} className="text-paper-500">
                  Loading…
                </TD>
              </TR>
            )}
            {items.map((s: Source) => (
              <TR key={s.id}>
                <TD>
                  <Link href={`/sources/${s.id}`} className="flex flex-col group">
                    <span className="text-paper-50 group-hover:text-accent-green font-medium transition-colors">
                      {s.name}
                    </span>
                    <span className="font-mono text-[11px] text-paper-500 group-hover:text-paper-400">{s.slug}</span>
                  </Link>
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
                  <button
                    type="button"
                    onClick={() => toggleActive.mutate({ id: s.id, is_active: !s.is_active })}
                    disabled={toggleActive.isPending}
                    title="Click to toggle active / paused"
                    className="focus:outline-none"
                  >
                    {s.is_active ? (
                      <Badge variant="green" className="cursor-pointer hover:opacity-80">Active</Badge>
                    ) : (
                      <Badge variant="muted" className="cursor-pointer hover:opacity-80">Paused</Badge>
                    )}
                  </button>
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
                  <Link
                    href={`/sources/${s.id}`}
                    className="group inline-flex items-center gap-1 hover:underline"
                    title={`View all articles from ${s.name}`}
                  >
                    <span className={s.total_articles_ingested > 0 ? "font-semibold text-paper-100 group-hover:text-accent-green" : "text-paper-500"}>
                      {s.total_articles_ingested}
                    </span>
                    <ExternalLink className="h-2.5 w-2.5 opacity-0 group-hover:opacity-100 text-accent-green transition-opacity" />
                  </Link>
                </TD>
                <TD className="text-right">
                  <div className="inline-flex items-center gap-2 justify-end">
                    <Link href={`/sources/${s.id}`}>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs text-paper-300 hover:text-paper-50"
                      >
                        View Feed
                      </Button>
                    </Link>
                    {Boolean(ingestedMap[s.id] && Date.now() - (ingestedMap[s.id] || 0) < 60000) && (
                      <Badge variant="green" className="flex items-center gap-1 text-[11px] animate-pulse">
                        <Check className="h-3 w-3" /> Ingested
                      </Badge>
                    )}
                    <Button
                      variant="subtle"
                      size="sm"
                      disabled={!s.is_active || (ingestingId === s.id || ingestingId === "all")}
                      onClick={() => ingestOne.mutate(s.id)}
                      className="min-w-[70px] h-8"
                    >
                      {ingestingId === s.id || ingestingId === "all" ? (
                        <span className="flex items-center gap-1 text-accent-green">
                          <RefreshCw className="h-3 w-3 animate-spin" /> Ingesting…
                        </span>
                      ) : (
                        "Ingest"
                      )}
                    </Button>
                  </div>
                </TD>
              </TR>
            ))}
            {!isLoading && items.length === 0 && (
              <TR>
                <TD colSpan={9} className="text-paper-500">
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
