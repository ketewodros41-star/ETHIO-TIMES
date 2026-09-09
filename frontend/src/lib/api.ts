import type {
  Article,
  IngestTriggerResponse,
  Page,
  Source,
  SourceHealth,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
};

export { API_BASE };
