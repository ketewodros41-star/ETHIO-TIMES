import type {
  Article,
  IngestTriggerResponse,
  NewsEvent,
  NewsEventDetail,
  Page,
  PipelineStats,
  Source,
  SourceHealth,
} from "./types";

const API_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE_URL ?? "")
    : (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000");

const API_PREFIX = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () =>
    request<{ status: string; service: string; database: string }>("/health"),

  listSources: (params: {
    limit?: number;
    offset?: number;
    is_active?: boolean;
    source_type?: string;
    search?: string;
  }) => request<Page<Source>>(`/sources${qs(params)}`),

  getSource: (id: string) => request<Source>(`/sources/${id}`),

  sourceHealth: () => request<SourceHealth[]>("/source-health"),

  listArticles: (params: {
    limit?: number;
    offset?: number;
    source_id?: string;
    status?: string;
    search?: string;
  }) => request<Page<Article>>(`/articles${qs(params)}`),

  triggerIngest: (source_id?: string) =>
    request<IngestTriggerResponse>("/ingest/trigger", {
      method: "POST",
      body: JSON.stringify({ source_id: source_id ?? null }),
    }),

  listEvents: (params: {
    limit?: number;
    offset?: number;
    status?: string;
    category?: string;
    search?: string;
    verification_status?: string;
    review_required?: boolean;
    trend_status?: string;
    breaking?: boolean;
    sort?: "last_seen" | "trend_score";
  }) => request<Page<NewsEvent>>(`/events${qs(params)}`),

  getEvent: (id: string) => request<NewsEventDetail>(`/events/${id}`),

  clearReview: (eventId: string, reason: string) =>
    request<NewsEventDetail>(`/events/${eventId}/clear-review`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  createSource: (body: {
    name: string;
    website?: string;
    rss_url?: string;
    source_type: string;
    crawl_frequency_minutes?: number;
    is_active?: boolean;
  }) =>
    request<Source>("/sources", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateSource: (
    id: string,
    body: {
      is_active?: boolean;
      crawl_frequency_minutes?: number;
      name?: string;
      website?: string;
    },
  ) =>
    request<Source>(`/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  pipelineStats: () => request<PipelineStats>("/pipeline/stats"),
};

export const postsApi = {
  list: (params?: { limit?: number; offset?: number; status?: string; event_id?: string; theme?: string }) =>
    request<Page<import('./types').SocialPost>>("/posts" + qs(params || {})),
  get: (id: string) => request<import('./types').SocialPost>(`/posts/${id}`),
  compose: (body: { event_id: string; format: string; theme?: string }) =>
    request<import('./types').ComposeTaskResponse>("/posts/compose", { method: "POST", body: JSON.stringify(body) }),
  triggerRender: (id: string) =>
    request<import('./types').ComposeTaskResponse>(`/posts/${id}/render`, { method: "POST" }),
  triggerPublish: (id: string) =>
    request<import('./types').ComposeTaskResponse>(`/posts/${id}/publish`, { method: "POST" }),
  schedule: (id: string, scheduled_at: string) =>
    request<import('./types').SocialPost>(`/posts/${id}/schedule`, { method: "POST", body: JSON.stringify({ scheduled_at }) }),
  patch: (id: string, body: { headline?: string; caption?: string; hashtags?: string[] }) =>
    request<import('./types').SocialPost>(`/posts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/posts/${id}`, { method: "DELETE" }),
  checkEligibility: (id: string) => request<import('./types').EligibilityCheck>(`/posts/${id}/eligibility`),
  generateAsset: (event_id: string) =>
    request<import('./types').ComposeTaskResponse>(`/posts/assets/generate${qs({ event_id })}`, { method: "POST" }),
  listAssets: (event_id: string) =>
    request<import('./types').VisualAsset[]>(`/posts/assets${qs({ event_id })}`),
  selectAsset: (asset_id: string) =>
    request<import('./types').VisualAsset>(`/posts/assets/${asset_id}/select`, { method: "POST" }),
};

export { API_BASE };
