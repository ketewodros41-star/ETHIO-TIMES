/**
 * Playwright render target.
 *
 * This route is screenshot by the backend RenderService to produce
 * final Instagram PNGs. No nav, no layout, no scroll.
 * Access: /render/{post_id}?format=portrait
 */
import { notFound } from "next/navigation";
import type { InstagramFormat } from "@/templates/instagram/formats";
import { PostTemplate } from "@/templates/instagram/PostTemplate";
import type { PostTemplateData } from "@/templates/instagram/PostTemplate";

async function getPost(postId: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  try {
    const res = await fetch(`${apiUrl}/posts/${postId}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function RenderPage({
  params,
  searchParams,
}: {
  params: { post_id: string };
  searchParams: { format?: string };
}) {
  const post = await getPost(params.post_id);
  if (!post) notFound();

  const format = (["portrait", "square", "story"].includes(searchParams.format ?? "")
    ? searchParams.format
    : "portrait") as InstagramFormat;

  const data: PostTemplateData = {
    category: post.event?.primary_category ?? "News",
    headline: post.headline,
    dek: post.key_facts?.[0] ?? undefined,
    source: post.source_attribution ?? "ETHIOTIMES",
    dateLabel: new Date(post.created_at).toLocaleDateString("en-US", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).toUpperCase(),
    imageUrl: post.visual_asset?.storage_url ?? undefined,
    theme: post.theme as any,
  };

  return (
    <div style={{ margin: 0, padding: 0, background: "#0B0C0E" }}>
      <PostTemplate format={format} data={data} />
    </div>
  );
}
