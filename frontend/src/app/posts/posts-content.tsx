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
              <Card key={post.id} className="p-4 transition-colors hover:border-ink-600">
                <div className="flex gap-4">
                  {/* Thumbnail */}
                  <div className="h-24 w-24 shrink-0 rounded-sm bg-ink-800 border border-ink-700 overflow-hidden relative flex items-center justify-center">
                    {post.media_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={post.media_url} alt="" className="object-cover w-full h-full" />
                    ) : (
                      <span className="text-[10px] text-paper-500 font-mono text-center px-1 break-words w-full uppercase">
                        {post.theme}
                      </span>
                    )}
                  </div>

                  {/* Main Content */}
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="muted">{post.theme.replace("_", " ")}</Badge>
                      <Badge variant="outline">{post.format}</Badge>
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
                            variant="secondary" 
                            size="sm"
                            disabled={renderMutation.isPending}
                            onClick={() => renderMutation.mutate(post.id)}
                          >
                            Render
                          </Button>
                          <Button 
                            variant="destructive" 
                            size="sm"
                            disabled={deleteMutation.isPending}
                            onClick={() => deleteMutation.mutate(post.id)}
                          >
                            Delete
                          </Button>
                        </>
                      )}
                      {post.status === "rendered" && (
                        <Button 
                          variant="default" 
                          size="sm"
                          disabled={publishMutation.isPending || (post.eligibility_snapshot && post.eligibility_snapshot.review_required)}
                          onClick={() => publishMutation.mutate(post.id)}
                        >
                          Publish
                        </Button>
                      )}
                      {post.status === "failed" && (
                        <Button 
                          variant="secondary" 
                          size="sm"
                          disabled={renderMutation.isPending}
                          onClick={() => renderMutation.mutate(post.id)}
                        >
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PageShell>
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
