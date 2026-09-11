"use client";

import { useState } from "react";
import { PageShell } from "@/components/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SocialPost } from "@/lib/types";
import { postsApi } from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const STATUS_FILTERS = ["all", "draft", "rendered", "scheduled", "published", "failed"];

export function PostsContent() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["posts", status],
    queryFn: () => postsApi.list(status !== "all" ? { status } : {}),
  });

  const renderMutation = useMutation({
    mutationFn: (id: string) => postsApi.triggerRender(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => postsApi.triggerPublish(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => postsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const items = data?.items ?? [];

  return (
    <PageShell title="Posts">
      <div className="space-y-4">
        {/* Filters */}
        <div className="flex gap-2">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1.5 rounded-card text-sm font-medium transition-colors ${
                status === s
                  ? "bg-ink-700 text-paper-50"
                  : "text-paper-500 hover:text-paper-300 hover:bg-ink-800"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="text-paper-500 text-sm">Loading posts...</div>
        ) : items.length === 0 ? (
          <Card className="p-8 text-center text-sm text-paper-500">
            No posts found.
          </Card>
        ) : (
          <div className="space-y-4">
            {items.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onRender={() => renderMutation.mutate(post.id)}
                onPublish={() => publishMutation.mutate(post.id)}
                onDelete={() => deleteMutation.mutate(post.id)}
                isRendering={renderMutation.isPending}
                isPublishing={publishMutation.isPending}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}

function PostCard({
  post,
  onRender,
  onPublish,
  onDelete,
  isRendering,
  isPublishing,
  isDeleting,
}: {
  post: SocialPost;
  onRender: () => void;
  onPublish: () => void;
  onDelete: () => void;
  isRendering: boolean;
  isPublishing: boolean;
  isDeleting: boolean;
}) {
  const slides = post.carousel_slides ?? [];
  const hasCarousel = slides.length > 0;
  const [slideIdx, setSlideIdx] = useState(0);
  const [showSlideViewer, setShowSlideViewer] = useState(false);

  const currentSlide = slides[slideIdx];

  return (
    <Card className="p-4 transition-colors hover:border-ink-600">
      <div className="flex gap-4">
        {/* Thumbnail */}
        <div className="h-24 w-24 shrink-0 rounded-sm bg-ink-800 border border-ink-700 overflow-hidden relative flex flex-col items-center justify-center p-1 text-center">
          {post.media_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={post.media_url} alt="" className="object-cover w-full h-full" />
          ) : (
            <>
              <span className="text-[10px] text-paper-400 font-mono uppercase">
                {post.theme.replace("_", " ")}
              </span>
              {hasCarousel && (
                <span className="text-[9px] text-accent-green font-mono mt-1">
                  {slides.length} slides
                </span>
              )}
            </>
          )}
        </div>

        {/* Main Content */}
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="muted">{post.theme.replace("_", " ")}</Badge>
            <Badge variant="muted">{post.format}</Badge>
            {hasCarousel && (
              <Badge variant="green">{slides.length} Slides Carousel</Badge>
            )}
            <span className="text-xs text-paper-500 ml-2">
              {new Date(post.created_at).toLocaleDateString()}
            </span>
          </div>

          <h3 className="font-display text-lg font-medium text-paper-50 leading-snug">
            {post.headline}
          </h3>

          <p className="text-sm text-paper-300 line-clamp-1">{post.caption}</p>

          {post.source_attribution && (
            <p className="text-xs text-paper-500 uppercase tracking-label font-mono">
              Source: {post.source_attribution}
            </p>
          )}

          {/* Carousel Slide Viewer Toggle & Strip */}
          {hasCarousel && (
            <div className="mt-3 pt-2 border-t border-ink-800">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowSlideViewer(!showSlideViewer)}
                  className="text-xs font-mono text-accent-green hover:underline flex items-center gap-1"
                >
                  {showSlideViewer ? "Hide Carousel Slides" : "Inspect Carousel Slides →"}
                </button>
                {showSlideViewer && currentSlide && (
                  <div className="flex items-center gap-2 text-xs font-mono text-paper-400">
                    <button
                      type="button"
                      disabled={slideIdx === 0}
                      onClick={() => setSlideIdx((i) => Math.max(0, i - 1))}
                      className="px-2 py-0.5 rounded bg-ink-800 border border-ink-700 disabled:opacity-30 hover:bg-ink-700"
                    >
                      ←
                    </button>
                    <span>
                      {slideIdx + 1} / {slides.length}
                    </span>
                    <button
                      type="button"
                      disabled={slideIdx === slides.length - 1}
                      onClick={() => setSlideIdx((i) => Math.min(slides.length - 1, i + 1))}
                      className="px-2 py-0.5 rounded bg-ink-800 border border-ink-700 disabled:opacity-30 hover:bg-ink-700"
                    >
                      →
                    </button>
                  </div>
                )}
              </div>

              {showSlideViewer && currentSlide && (
                <div className="mt-2 rounded border border-ink-700 bg-ink-850 p-3 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-mono text-paper-400">
                    <span className="uppercase text-accent-green font-semibold">
                      Slide {currentSlide.slide_number}: {currentSlide.slide_type.replace("_", " ")}
                    </span>
                    <span>Accent: {currentSlide.accent}</span>
                  </div>
                  <p className="text-sm font-semibold text-paper-100">{currentSlide.header}</p>
                  {currentSlide.body_text && (
                    <p className="text-xs text-paper-300">{currentSlide.body_text}</p>
                  )}
                  {currentSlide.bullet_points && currentSlide.bullet_points.length > 0 && (
                    <ul className="text-xs text-paper-300 list-disc list-inside space-y-0.5">
                      {currentSlide.bullet_points.map((pt, idx) => (
                        <li key={idx}>{pt}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Status & Actions */}
        <div className="shrink-0 flex flex-col items-end justify-between min-w-[140px]">
          <div className="flex flex-col items-end gap-2">
            <PostStatusBadge status={post.status} />
            <EligibilityBadge snapshot={post.eligibility_snapshot} />
          </div>

          <div className="flex items-center gap-2 mt-4">
            {post.status === "draft" && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isRendering}
                  onClick={onRender}
                >
                  {isRendering ? "Rendering…" : "Render"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-signal-red hover:bg-signal-red/10"
                  disabled={isDeleting}
                  onClick={onDelete}
                >
                  Delete
                </Button>
              </>
            )}
            {post.status === "rendered" && (
              <Button
                variant="default"
                size="sm"
                disabled={isPublishing || (post.eligibility_snapshot && post.eligibility_snapshot.review_required)}
                onClick={onPublish}
              >
                {isPublishing ? "Publishing…" : "Publish"}
              </Button>
            )}
            {post.status === "failed" && (
              <Button
                variant="outline"
                size="sm"
                disabled={isRendering}
                onClick={onRender}
              >
                Retry
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function PostStatusBadge({ status }: { status: SocialPost["status"] }) {
  const map: Record<SocialPost["status"], { label: string; variant: "default" | "muted" | "green" | "red" | "gold" }> = {
    draft: { label: "Draft", variant: "muted" },
    rendered: { label: "Rendered", variant: "default" },
    scheduled: { label: "Scheduled", variant: "gold" },
    published: { label: "Published", variant: "green" },
    failed: { label: "Failed", variant: "red" },
  };
  const { label, variant } = map[status] ?? { label: status, variant: "default" };
  return <Badge variant={variant}>{label}</Badge>;
}

function EligibilityBadge({ snapshot }: { snapshot?: SocialPost["eligibility_snapshot"] }) {
  if (!snapshot) return null;
  if (snapshot.event_verification_status === "contradicted") {
    return <span className="text-[10px] text-signal-red uppercase font-mono tracking-wide">✗ Contradicted</span>;
  }
  if (snapshot.review_required) {
    return <span className="text-[10px] text-accent-gold uppercase font-mono tracking-wide">⚠ Review req</span>;
  }
  if (snapshot.auto_publish_eligible) {
    return <span className="text-[10px] text-accent-green uppercase font-mono tracking-wide">✓ Auto-eligible</span>;
  }
  return <span className="text-[10px] text-paper-500 uppercase font-mono tracking-wide">⧖ Pending</span>;
}
