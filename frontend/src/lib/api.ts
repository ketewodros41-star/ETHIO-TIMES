import type {
  Article,
  IngestStopResponse,
  IngestTriggerResponse,
  NewsEvent,
  NewsEventDetail,
  Page,
  PipelineStats,
  Source,
  SourceHealth,
} from "./types";

const DEFAULT_BACKEND_URL = "https://ethiotimes-backend.onrender.com";

function getApiBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (envUrl && !envUrl.includes("localhost:8000") && !envUrl.includes("127.0.0.1:8000")) {
    return envUrl;
  }
  return DEFAULT_BACKEND_URL;
}

const API_BASE =
  typeof window !== "undefined"
    ? getApiBase()
    : (process.env.BACKEND_URL || getApiBase());

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
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((err: { msg?: string; message?: string }) => err.msg || err.message || JSON.stringify(err))
          .join("; ");
      } else if (body.detail) {
        detail = JSON.stringify(body.detail);
      }
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
    category?: string;
    sort?: string;
  }) => request<Page<Article>>(`/articles${qs(params)}`),

  getArticle: (id: string) => request<Article>(`/articles/${id}`),

  ensureArticleEvent: (articleId: string) =>
    request<NewsEvent>(`/articles/${articleId}/ensure-event`, {
      method: "POST",
    }),

  triggerIngest: (source_id?: string) =>
    request<IngestTriggerResponse>("/ingest/trigger", {
      method: "POST",
      body: JSON.stringify({ source_id: source_id ?? null }),
    }),

  stopIngest: (source_id?: string) =>
    request<IngestStopResponse>("/ingest/stop", {
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
    sort?: string;
    scope?: "ethiopia" | "neighboring" | "international" | "all";
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
    telegram_username?: string;
    telegram_url?: string;
    source_type: string;
    crawl_frequency_minutes?: number;
    refresh_tier?: "urgent" | "high" | "standard" | "low";
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
      refresh_tier?: "urgent" | "high" | "standard" | "low";
      name?: string;
      website?: string;
    },
  ) =>
    request<Source>(`/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteSource: (id: string) =>
    request<void>(`/sources/${id}`, {
      method: "DELETE",
    }),

  pruneStaleData: (jobs_max_age_days: number = 7, articles_max_age_days: number = 60) =>
    request<{ deleted_jobs: number; deleted_articles: number; message: string }>(
      `/pipeline/prune-stale${qs({ jobs_max_age_days, articles_max_age_days })}`,
      { method: "POST" }
    ),

  pipelineStats: () => request<PipelineStats>("/pipeline/stats"),

  getPublishingSettings: () => request<import("./types").PublishingSettings>("/settings/publishing"),
  updatePublishingSettings: (body: Partial<Pick<import("./types").PublishingSettings, "posts_per_day" | "automation_enabled" | "timezone">>) =>
    request<import("./types").PublishingSettings>("/settings/publishing", { method: "PATCH", body: JSON.stringify(body) }),
  getTelegramPublishingSettings: () => request<import("./types").TelegramPublishingSettings>("/settings/telegram-publishing"),
  updateTelegramPublishingSettings: (body: Partial<Omit<import("./types").TelegramPublishingSettings, "bot_configured" | "updated_at">>) =>
    request<import("./types").TelegramPublishingSettings>("/settings/telegram-publishing", { method: "PATCH", body: JSON.stringify(body) }),
  updateContentFilters: (body: Record<string, import("./types").BucketContentFilter>) =>
    request<import("./types").TelegramPublishingSettings>("/settings/telegram-publishing/content-filters", { method: "PUT", body: JSON.stringify(body) }),
  testTelegramPost: (body?: { event_id?: string; force_live?: boolean; channel_username?: string; stream?: string; category?: string }) =>
    request<import("./types").TelegramTestPostResponse>("/settings/telegram-publishing/test-post", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
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
  fetchArticlePhoto: (event_id: string) =>
    request<import('./types').ComposeTaskResponse>(`/posts/assets/fetch-article-photo${qs({ event_id })}`, { method: "POST" }),
  browsePhotos: (eventId: string, query?: string, page: number = 1) =>
    request<import('./types').PhotoBrowseResponse>(`/posts/assets/browse-photos${qs({ event_id: eventId, page, ...(query ? { query } : {}) })}`),
  selectCandidate: (body: import('./types').SelectCandidateRequest) =>
    request<import('./types').VisualAsset>('/posts/assets/select-candidate', {
      method: "POST",
      body: JSON.stringify(body),
    }),
  searchPhotos: (event_id: string, query?: string) =>
    request<import('./types').VisualAsset[]>(`/posts/assets/search-photos${qs({ event_id, ...(query ? { query } : {}) })}`, { method: "POST" }),
  listAssets: (event_id: string) =>
    request<import('./types').VisualAsset[]>(`/posts/assets${qs({ event_id })}`),
  selectAsset: (asset_id: string) =>
    request<import('./types').VisualAsset>(`/posts/assets/${asset_id}/select`, { method: "POST" }),
  deleteAsset: (asset_id: string) =>
    request<void>(`/posts/assets/${asset_id}`, { method: "DELETE" }),
  translateEditorial: (body: import('./types').EditorialTranslationRequest) =>
    request<import('./types').EditorialTranslationResponse>('/posts/translate-editorial', {
      method: "POST",
      body: JSON.stringify(body),
    }),
};


export const eventsApi = {
  latestTimestamp: () =>
    request<{ latest_at: string | null; total_count: number }>("/events/latest-timestamp"),
};

export { API_BASE };
