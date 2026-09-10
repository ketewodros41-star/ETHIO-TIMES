"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Calendar,
  Clock,
  ExternalLink,
  Globe,
  Newspaper,
  Play,
  Radio,
  RefreshCw,
  Rss,
  Send,
  ShieldCheck,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  HealthDot,
  ProcessingBadge,
  RelevanceBadge,
  RelevanceMeter,
  VerificationBadge,
} from "@/components/status";
import { formatDate, relativeTime } from "@/lib/utils";

const PAGE_SIZE = 25;

export function SourceDetailContent({ id }: { id: string }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  // Fetch Source Details
  const {
    data: source,
    isLoading: isSourceLoading,
    error: sourceError,
    refetch: refetchSource,
  } = useQuery({
    queryKey: ["source", id],
    queryFn: () => api.getSource(id),
  });

  // Fetch Articles for this Source
  const {
    data: articlesData,
    isLoading: isArticlesLoading,
    refetch: refetchArticles,
    isFetching: isArticlesFetching,
  } = useQuery({
    queryKey: ["articles", "source", id, search, page],
    queryFn: () =>
      api.listArticles({
        source_id: id,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        search: search || undefined,
      }),
    refetchInterval: 120_000,
    refetchIntervalInBackground: false,
  });

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }

  // Trigger Ingestion for this source
  const ingestOne = useMutation({
    mutationFn: () => api.triggerIngest(id),
    onSuccess: (res) => {
      flash(res.message || "Ingestion triggered for this source.");
      setTimeout(() => {
        void refetchSource();
        void refetchArticles();
      }, 2000);
      setTimeout(() => {
        void refetchSource();
        void refetchArticles();
      }, 6000);
    },
    onError: (e: Error) => flash(`Ingest failed: ${e.message}`),
  });

  // Toggle active / paused
  const toggleActive = useMutation({
    mutationFn: (is_active: boolean) => api.updateSource(id, { is_active }),
    onSuccess: (updated) => {
      flash(`Source "${updated.name}" is now ${updated.is_active ? "active" : "paused"}.`);
      void qc.invalidateQueries({ queryKey: ["source", id] });
      void qc.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (e: Error) => flash(`Failed to update status: ${e.message}`),
  });

  if (isSourceLoading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-paper-500 justify-center">
        <RefreshCw className="h-5 w-5 animate-spin text-accent-green" />
        <span>Loading news source profile…</span>
      </div>
    );
  }

  if (sourceError || !source) {
    return (
      <Card className="p-8 text-center space-y-3 border-red-500/30 bg-red-950/20">
        <h3 className="font-display text-lg text-red-400">News Source Not Found</h3>
        <p className="text-sm text-paper-400">
          The requested news source ID could not be loaded or does not exist.
        </p>
        <Link href="/sources">
          <Button variant="outline" size="sm" className="mt-2">
            <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Sources
          </Button>
        </Link>
      </Card>
    );
  }

  const articles = articlesData?.items ?? [];
  const totalArticles = articlesData?.meta.total ?? source.total_articles_ingested ?? 0;
  const maxPage = Math.max(0, Math.ceil(totalArticles / PAGE_SIZE) - 1);

  return (
    <div className="space-y-6">
      {/* Back Navigation Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/sources"
          className="inline-flex items-center gap-1.5 text-xs text-paper-400 hover:text-paper-100 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to All Sources
        </Link>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-paper-400 bg-ink-800 border border-ink-700 px-2.5 py-1 rounded-full">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-green animate-pulse" />
            Live Sync: 2m
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void refetchSource();
              void refetchArticles();
            }}
            disabled={isArticlesFetching}
            className="flex items-center gap-1.5 text-xs"
          >
            <RefreshCw
              className={`h-3 w-3 ${isArticlesFetching ? "animate-spin text-accent-green" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {toast && (
        <div className="rounded-card border border-accent-green/40 bg-accent-green/10 px-4 py-2.5 text-sm text-accent-green flex items-center gap-2">
          <Check className="h-4 w-4 shrink-0" />
          <span>{toast}</span>
        </div>
      )}

      {/* Publisher Profile Hero Card */}
      <Card className="p-6 border-ink-600 bg-ink-900/90 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="h-14 w-14 rounded-card bg-ink-800 border border-ink-600 flex items-center justify-center text-xl font-bold text-accent-green shrink-0 shadow-inner">
              {source.source_type === "telegram_channel" ? (
                <Send className="h-7 w-7 text-accent-gold" />
              ) : source.rss_url ? (
                <Rss className="h-7 w-7 text-accent-green" />
              ) : (
                <Radio className="h-7 w-7 text-paper-300" />
              )}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-display text-2xl font-bold text-paper-50 tracking-tight">
                  {source.name}
                </h1>
                <VerificationBadge status={source.verification_status} />
                <button
                  type="button"
                  onClick={() => toggleActive.mutate(!source.is_active)}
                  disabled={toggleActive.isPending}
                  title="Click to toggle active / paused"
                >
                  {source.is_active ? (
                    <Badge variant="green" className="cursor-pointer hover:opacity-80">
                      Active
                    </Badge>
                  ) : (
                    <Badge variant="muted" className="cursor-pointer hover:opacity-80">
                      Paused
                    </Badge>
                  )}
                </button>
              </div>
              <p className="font-mono text-xs text-paper-400 mt-1">
                slug: <span className="text-paper-200">{source.slug}</span> ·{" "}
                <span className="capitalize">{source.source_type.replace(/_/g, " ")}</span> ·{" "}
                Language: <span className="uppercase">{source.language}</span> · Country:{" "}
                <span className="uppercase">{source.country}</span>
              </p>
              {source.description && (
                <p className="text-xs text-paper-300 mt-2 max-w-2xl leading-relaxed">
                  {source.description}
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => ingestOne.mutate()}
              disabled={ingestOne.isPending || !source.is_active}
              className="flex items-center gap-1.5"
            >
              {ingestOne.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-ink-950" />
                  <span>Ingesting…</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span>Ingest Now</span>
                </>
              )}
            </Button>
            {source.website && (
              <a
                href={source.website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-card border border-ink-600 bg-ink-800 text-xs font-medium text-paper-200 hover:text-paper-50 hover:border-ink-500 transition-colors"
              >
                <Globe className="h-3.5 w-3.5 text-accent-green" /> Website{" "}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
            {source.rss_url && (
              <a
                href={source.rss_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-card border border-ink-600 bg-ink-800 text-xs font-medium text-paper-200 hover:text-paper-50 hover:border-ink-500 transition-colors"
              >
                <Rss className="h-3.5 w-3.5 text-accent-gold" /> RSS Feed{" "}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
            {source.telegram_url && (
              <a
                href={source.telegram_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-card border border-ink-600 bg-ink-800 text-xs font-medium text-paper-200 hover:text-paper-50 hover:border-ink-500 transition-colors"
              >
                <Send className="h-3.5 w-3.5 text-sky-400" /> Telegram{" "}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>

        {/* Quick Ingestion & Reliability Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-ink-750">
          <div className="rounded-card bg-ink-850 p-3 border border-ink-700">
            <span className="text-[11px] uppercase tracking-label font-mono text-paper-400">
              Total Ingested
            </span>
            <div className="text-xl font-bold font-mono text-paper-50 mt-1">
              {totalArticles}
            </div>
          </div>
          <div className="rounded-card bg-ink-850 p-3 border border-ink-700">
            <span className="text-[11px] uppercase tracking-label font-mono text-paper-400">
              Health Status
            </span>
            <div className="mt-1 flex items-center">
              <HealthDot status={source.health_status} />
            </div>
          </div>
          <div className="rounded-card bg-ink-850 p-3 border border-ink-700">
            <span className="text-[11px] uppercase tracking-label font-mono text-paper-400">
              Crawl Frequency
            </span>
            <div className="text-sm font-semibold text-paper-200 mt-1">
              Every {source.crawl_frequency_minutes} min
            </div>
          </div>
          <div className="rounded-card bg-ink-850 p-3 border border-ink-700">
            <span className="text-[11px] uppercase tracking-label font-mono text-paper-400">
              Last Checked
            </span>
            <div className="text-sm font-semibold text-paper-200 mt-1">
              {relativeTime(source.last_checked_at)}
            </div>
          </div>
        </div>
      </Card>

      {/* Ingested News Feed Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-accent-green" />
            <h2 className="font-display text-lg font-semibold text-paper-50">
              Ingested News Feed ({totalArticles})
            </h2>
          </div>
          <Input
            placeholder={`Search ${source.name} headlines…`}
            value={search}
            onChange={(e) => {
              setPage(0);
              setSearch(e.target.value);
            }}
            className="max-w-xs"
          />
        </div>

        {isArticlesLoading && (
          <div className="flex items-center gap-2 py-10 text-sm text-paper-500 justify-center">
            <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
            <span>Loading articles for {source.name}…</span>
          </div>
        )}

        {!isArticlesLoading && articles.length === 0 && (
          <Card className="p-10 text-center space-y-3">
            <p className="text-sm text-paper-400">
              {search
                ? `No articles match "${search}" for this publisher.`
                : `No articles have been ingested from ${source.name} yet.`}
            </p>
            {!search && source.is_active && (
              <Button
                size="sm"
                onClick={() => ingestOne.mutate()}
                disabled={ingestOne.isPending}
                className="mt-2"
              >
                <Play className="h-4 w-4 mr-1.5" /> Ingest From {source.name} Now
              </Button>
            )}
          </Card>
        )}

        <div className="space-y-3">
          {articles.map((a) => (
            <Card key={a.id} className="p-4 hover:border-ink-500 transition-colors">
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
                  <h3 className="font-display text-base md:text-lg font-medium leading-snug text-paper-50">
                    {a.title ?? "(untitled)"}
                  </h3>
                  {a.summary && (
                    <p className="mt-1.5 line-clamp-2 text-sm text-paper-300 leading-relaxed">
                      {a.summary}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-paper-500">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {formatDate(a.published_at ?? a.created_at)}
                    </span>
                    {a.author && <span>· By {a.author}</span>}
                    {a.url && (
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-accent-green hover:underline font-medium ml-auto"
                      >
                        Original Story <ExternalLink className="h-3 w-3" />
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

        {totalArticles > PAGE_SIZE && (
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
    </div>
  );
}
