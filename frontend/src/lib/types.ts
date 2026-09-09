// Mirrors backend Pydantic schemas (app/schemas).

export type SourceType =
  | "government"
  | "government_agency"
  | "national_news_agency"
  | "public_broadcaster"
  | "independent_media"
  | "business_media"
  | "international_wire"
  | "international_media"
  | "research_institution"
  | "financial_institution"
  | "social_signal"
  | "telegram_channel";

export type SourceHealthStatus =
  | "unknown"
  | "healthy"
  | "degraded"
  | "failing"
  | "disabled";

export type VerificationStatus =
  | "verified"
  | "needs_verification"
  | "unverified";

export type ArticleStatus = "raw" | "normalized" | "duplicate" | "discarded";

export type ProcessingStatus =
  | "pending"
  | "relevance_scored"
  | "analyzed"
  | "embedded"
  | "clustered"
  | "skipped_irrelevant"
  | "failed"
  | "dead_letter";

export type RelevanceDecision = "relevant" | "borderline" | "irrelevant";

export type EventStatus =
  | "developing"
  | "confirmed"
  | "updated"
  | "dormant"
  | "closed";

export type ArticleRelationType =
  | "primary"
  | "duplicate"
  | "related"
  | "follow_up"
  | "context";

export type EventTimelineType =
  | "first_report"
  | "source_confirmation"
  | "new_development"
  | "correction";

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface Source {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  website?: string | null;
  base_url?: string | null;
  rss_url?: string | null;
  api_url?: string | null;
  telegram_username?: string | null;
  telegram_url?: string | null;
  source_type: SourceType;
  country: string;
  language: string;
  trust_profile: Record<string, unknown>;
  coverage_categories: string[];
  ethiopia_relevance_score: number;
  is_primary_source: boolean;
  verification_status: VerificationStatus;
  verification_notes?: string | null;
  is_active: boolean;
  crawl_frequency_minutes: number;
  health_status: SourceHealthStatus;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error_message?: string | null;
  consecutive_failures: number;
  total_articles_ingested: number;
  created_at: string;
  updated_at: string;
}

export interface SourceHealth {
  id: string;
  slug: string;
  name: string;
  source_type: SourceType;
  is_active: boolean;
  health_status: SourceHealthStatus;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error_message?: string | null;
  consecutive_failures: number;
  total_articles_ingested: number;
}

export interface Article {
  id: string;
  source_id: string;
  canonical_url: string;
  url?: string | null;
  title?: string | null;
  summary?: string | null;
  author?: string | null;
  language?: string | null;
  categories: string[];
  image_url?: string | null;
  ethiopia_relevance_score: number;
  relevance_keywords: string[];
  status: ArticleStatus;
  published_at?: string | null;
  fetched_at?: string | null;
  created_at: string;
  processing_status: ProcessingStatus;
  relevance_score?: number | null;
  relevance_decision?: RelevanceDecision | null;
  is_ethiopia_related?: boolean | null;
  primary_region?: string | null;
  detected_language?: string | null;
  importance_score: number;
}

export interface SourceRef {
  id: string;
  name: string;
  slug: string;
}

export interface ArticleSummary {
  id: string;
  title?: string | null;
  summary?: string | null;
  url?: string | null;
  published_at?: string | null;
  detected_language?: string | null;
  importance_score: number;
  relevance_score?: number | null;
  relevance_decision?: RelevanceDecision | null;
  processing_status: ProcessingStatus;
  category?: string | null;
  source?: SourceRef | null;
}

export interface EventArticleLink {
  relation_type: ArticleRelationType;
  similarity_score: number;
  confidence: number;
  is_primary: boolean;
  article: ArticleSummary;
}

export interface EventTimelineEntry {
  id: string;
  entry_type: EventTimelineType;
  occurred_at: string;
  title?: string | null;
  detail: Record<string, unknown>;
  article_id?: string | null;
}

export interface NewsEvent {
  id: string;
  title: string;
  summary?: string | null;
  slug?: string | null;
  status: EventStatus;
  primary_category?: string | null;
  primary_region?: string | null;
  categories: string[];
  key_entities: string[];
  significance_score: number;
  cluster_confidence: number;
  article_count: number;
  source_count: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface NewsEventDetail extends NewsEvent {
  articles: EventArticleLink[];
  timeline: EventTimelineEntry[];
}

export interface PipelineStats {
  total_articles: number;
  embedded: number;
  ethiopia_related: number;
  total_events: number;
  by_processing_status: Record<ProcessingStatus, number>;
}

export interface IngestTriggerResponse {
  enqueued: boolean;
  task_id?: string | null;
  source_ids: string[];
  message: string;
}
