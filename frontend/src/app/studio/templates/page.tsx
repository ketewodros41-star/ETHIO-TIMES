"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, postsApi } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ImageIcon, Sparkles, RefreshCw, Check, Palette, CheckCircle2,
  Search, Camera, Bot, Globe, X, Newspaper, Trash2, ChevronLeft, ChevronRight, User,
} from "lucide-react";
import {
  FORMATS, PortraitPost, SquarePost, StoryPost, CarouselCard,
  THEMES, THEME_IDS,
  type InstagramFormat, type ThemeId, type PostTemplateData, type CarouselSlideData,
} from "@/templates/instagram";
import type { VisualAsset, PhotoCandidate } from "@/lib/types";

const SAMPLE: PostTemplateData = {
  category: "Economy",
  headline: "National Bank signals shift as birr reforms take hold",
  dek: "Policymakers weigh the next phase of Ethiopia's macroeconomic overhaul amid cooling inflation.",
  source: "Addis Fortune",
  dateLabel: "9 SEP 2026",
  accent: "green",
  style: "Premium Magazine",
  theme: "verified_brief",
};

function ScaledPreview({ width, height, target, children }: {
  width: number; height: number; target: number; children: React.ReactNode;
}) {
  const scale = target / width;
  return (
    <div style={{ width: target, height: height * scale }}
      className="overflow-hidden rounded-card border border-ink-700 bg-ink-900 shadow-2xl relative">
      <div style={{ transform: `scale(${scale})`, transformOrigin: "top left", width, height }}>
        {children}
      </div>
    </div>
  );
}

function AssetSourceBadge({ asset }: { asset: VisualAsset }) {
  const report = asset.quality_report as Record<string, string> | null;
  const source = report?.image_source ?? "ai_generated";
  const provider = asset.provider ?? "ai_generated";
  if (provider === "real_photo" || source === "real_photo") return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700/50">
      <Camera className="h-2.5 w-2.5" /> Real
    </span>
  );
  if (provider === "pexels" || source === "pexels") return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">
      <Globe className="h-2.5 w-2.5" /> Pexels
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-purple-900/60 text-purple-300 border border-purple-700/50">
      <Bot className="h-2.5 w-2.5" /> AI
    </span>
  );
}

function PhotoSearchDialog({
  eventId,
  eventTitle,
  eventCategory,
  onClose,
  onSelect,
}: {
  eventId: string;
  eventTitle?: string;
  eventCategory?: string | null;
  onClose: () => void;
  onSelect: (assetId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [topic, setTopic] = useState("");
  const [detectedPerson, setDetectedPerson] = useState<string | null>(null);
  const [suggestedChips, setSuggestedChips] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [results, setResults] = useState<PhotoCandidate[]>([]);
  const [searched, setSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSearch = async (targetPage: number = 1, customQuery?: string) => {
    setSearching(true);
    setErrorMsg(null);
    const q = customQuery !== undefined ? customQuery : query;
    try {
      const res = await postsApi.browsePhotos(eventId, q.trim() || undefined, targetPage);
      setResults(res.items);
      setPage(res.page);
      setTotalPages(res.total_pages);
      setTotalItems(res.total_items);
      setHasNext(res.has_next);
      setHasPrev(res.has_prev);
      if (res.topic) setTopic(res.topic);
      if (res.detected_person) setDetectedPerson(res.detected_person);
      if (res.suggested_chips && res.suggested_chips.length > 0) setSuggestedChips(res.suggested_chips);
      setSearched(true);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load photos");
      setResults([]);
      setSearched(true);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectCandidate = async (candidate: PhotoCandidate) => {
    setImportingId(candidate.id);
    setErrorMsg(null);
    try {
      const asset = await postsApi.selectCandidate({
        event_id: eventId,
        image_url: candidate.image_url,
        title: candidate.title,
        photographer: candidate.photographer,
        source: candidate.source,
      });
      onSelect(asset.id);
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to import selected photo");
      setImportingId(null);
    }
  };

  useEffect(() => { handleSearch(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl bg-ink-900 border border-ink-700 rounded-card shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700">
          <div className="flex items-center gap-2.5">
            <Globe className="h-5 w-5 text-accent-green" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-base text-paper-100">Topic-Based Internet Photo Browsing</span>
                <Badge variant="green" className="text-[10px] font-mono">
                  6 Alternatives / Page
                </Badge>
                {totalItems > 0 && (
                  <Badge variant="muted" className="text-[10px] font-mono text-paper-400">
                    {totalItems} Available
                  </Badge>
                )}
              </div>
              <p className="text-xs text-paper-400 mt-0.5 truncate max-w-lg">
                {eventTitle ? (
                  <span>Story: <strong className="text-paper-200 font-medium">&ldquo;{eventTitle}&rdquo;</strong></span>
                ) : (
                  "Browse authentic web photos matching this story. Click any image to import to Studio."
                )}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-paper-500 hover:text-paper-200 transition-colors p-1">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* AI Story Understanding Banner */}
        <div className="px-6 py-2.5 bg-accent-green/10 border-b border-accent-green/20 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-xs">
            <Sparkles className="h-4 w-4 text-accent-green shrink-0 animate-pulse" />
            <span className="text-paper-400">Understood Topic:</span>
            <strong className="text-accent-green font-medium">
              {topic ? `"${topic}"` : "Analyzing article topic & key entities..."}
            </strong>
            {detectedPerson && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-900/60 text-purple-200 border border-purple-700/50">
                <User className="h-2.5 w-2.5" /> Person: {detectedPerson}
              </span>
            )}
          </div>
          {topic && (
            <span className="text-[10px] font-mono text-paper-400">
              Auto-matched to story &bull; No typing required
            </span>
          )}
        </div>

        <div className="px-6 py-3.5 border-b border-ink-800 bg-ink-950/50 space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch(1, query)}
              placeholder={topic ? `Filtered by story: "${topic}". Or type custom query...` : "Refine topic keywords..."}
              className="flex-1 h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-100 focus:border-accent-green focus:outline-none placeholder:text-paper-600"
            />
            <Button size="sm" disabled={searching || !!importingId} onClick={() => handleSearch(1, query)}
              className="h-9 px-4 bg-accent-green text-ink-950 font-semibold hover:bg-accent-green/90 flex items-center gap-1.5">
              {searching ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              {searching ? "Searching..." : "Search"}
            </Button>
            {query && (
              <Button size="sm" variant="outline" disabled={searching} onClick={() => { setQuery(""); handleSearch(1, ""); }}
                className="h-9 px-3 border-ink-700 text-paper-400 hover:text-paper-100 text-xs">
                Reset to Story
              </Button>
            )}
          </div>

          {/* Quick Suggested Filter Chips */}
          {suggestedChips.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
              <span className="text-[10px] text-paper-500 font-mono">Suggested filters:</span>
              {suggestedChips.map((chip) => (
                <button
                  key={chip}
                  disabled={searching || !!importingId}
                  onClick={() => {
                    setQuery(chip);
                    handleSearch(1, chip);
                  }}
                  className={`px-2 py-0.5 rounded-full text-[11px] transition-colors border ${
                    query.toLowerCase() === chip.toLowerCase()
                      ? "bg-accent-green/20 border-accent-green text-accent-green font-medium"
                      : "bg-ink-800 hover:bg-ink-700 border-ink-700 text-paper-300 hover:text-paper-100"
                  }`}
                >
                  {chip}
                </button>
              ))}
            </div>
          )}

          <p className="text-[11px] text-paper-500 font-mono">
            Direct article photos, Openverse & Wikimedia Commons archives. No assets are saved until you choose one.
          </p>
        </div>

        <div className="px-6 py-5 overflow-y-auto flex-1">
          {errorMsg && (
            <div className="mb-4 p-3 rounded-card bg-red-950/40 border border-red-800/60 text-xs text-red-300">
              {errorMsg}
            </div>
          )}

          {searching && (
            <div className="py-16 text-center space-y-3">
              <RefreshCw className="h-8 w-8 animate-spin text-accent-green mx-auto" />
              <p className="text-sm text-paper-300 font-medium">Searching internet for 6 topic-matched alternatives...</p>
              <p className="text-xs text-paper-500 font-mono">Analyzing story entities and querying editorial archives</p>
            </div>
          )}

          {!searching && searched && results.length === 0 && (
            <div className="py-16 text-center space-y-3">
              <Globe className="h-10 w-10 text-paper-700 mx-auto" />
              <p className="text-sm text-paper-300">No matching photos found on the web.</p>
              <p className="text-xs text-paper-500">Try refining the search query above with different English keywords.</p>
            </div>
          )}

          {!searching && results.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-paper-400 font-mono">
                <span>
                  Showing {results.length} of {totalItems} alternatives (Page {page} of {totalPages}):
                </span>
                <span className="text-[11px] text-accent-green font-semibold">Select 1 photo to import to Studio</span>
              </div>
              <div className="grid grid-cols-3 gap-3.5">
                {results.map((c) => {
                  const isImporting = importingId === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => !importingId && handleSelectCandidate(c)}
                      className={`group cursor-pointer overflow-hidden rounded-card border transition-all duration-200 bg-ink-950 flex flex-col ${
                        isImporting
                          ? "border-accent-green ring-2 ring-accent-green/40 opacity-90 pointer-events-none"
                          : "border-ink-700 hover:border-accent-green hover:shadow-lg hover:shadow-accent-green/5"
                      }`}
                    >
                      <div className="aspect-[4/3] w-full overflow-hidden bg-ink-900 relative">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={c.thumb_url}
                          alt={c.title}
                          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                          loading="lazy"
                        />
                        {/* Source badge */}
                        <div className="absolute top-2 left-2">
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border backdrop-blur-md ${
                            c.source === "telegram"
                              ? "bg-blue-900/80 text-blue-200 border-blue-600/60"
                              : c.source === "article"
                              ? "bg-emerald-900/80 text-emerald-200 border-emerald-600/60"
                              : c.source === "pexels"
                              ? "bg-indigo-900/80 text-indigo-200 border-indigo-600/60"
                              : "bg-amber-900/80 text-amber-200 border-amber-600/60"
                          }`}>
                            {c.source === "telegram" ? "Telegram" : c.source === "article" ? "Article Lead" : c.source === "pexels" ? "Pexels" : "Wikimedia"}
                          </span>
                        </div>

                        {/* Hover Overlay */}
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center p-3 text-center">
                          <CheckCircle2 className="h-6 w-6 text-accent-green mb-1.5" />
                          <span className="text-xs text-white font-semibold">Import & Select</span>
                          <span className="text-[10px] text-paper-300 font-mono mt-0.5">Add to Photo Studio</span>
                        </div>

                        {/* Importing State */}
                        {isImporting && (
                          <div className="absolute inset-0 bg-ink-950/85 backdrop-blur-xs flex flex-col items-center justify-center p-3 text-center">
                            <RefreshCw className="h-6 w-6 animate-spin text-accent-green mb-2" />
                            <span className="text-xs text-paper-100 font-semibold">Importing photo...</span>
                            <span className="text-[10px] text-paper-400 font-mono">Adding to Photo Studio</span>
                          </div>
                        )}
                      </div>

                      <div className="p-2.5 flex-1 flex flex-col justify-between">
                        <div className="text-xs font-medium text-paper-100 line-clamp-2" title={c.title}>
                          {c.title}
                        </div>
                        <div className="mt-1.5 pt-1.5 border-t border-ink-800 text-[10px] text-paper-500 font-mono flex items-center justify-between">
                          <span className="truncate max-w-[130px]" title={c.photographer}>📷 {c.photographer}</span>
                          <span className="text-accent-green/80 group-hover:text-accent-green font-semibold">Import →</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-3.5 border-t border-ink-800 bg-ink-950/70 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={searching || !hasPrev || !!importingId}
              onClick={() => handleSearch(page - 1)}
              className="h-8 px-3 text-xs border-ink-600 text-paper-200 hover:text-white flex items-center gap-1.5 disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </Button>
            <span className="text-xs text-paper-300 font-mono px-2 py-1 rounded bg-ink-900 border border-ink-700">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={searching || !hasNext || !!importingId}
              onClick={() => handleSearch(page + 1)}
              className="h-8 px-3 text-xs border-accent-green/60 text-accent-green hover:bg-accent-green/10 flex items-center gap-1.5 font-semibold disabled:opacity-40"
            >
              Next 6 Photos
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>

          <div className="flex items-center gap-3">
            <p className="text-[11px] text-paper-500 hidden sm:block">
              Selected photo will be saved as a high-resolution asset in your Photo Studio.
            </p>
            <Button variant="outline" size="sm" onClick={onClose} disabled={!!importingId} className="h-8 text-xs border-ink-600">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StudioContent() {
  const searchParams = useSearchParams();
  const queryEventId = searchParams.get("event_id") || "";
  const queryClient = useQueryClient();

  const [selectedEventId, setSelectedEventId] = useState<string>(queryEventId);
  const [postMode, setPostMode] = useState<"single" | "carousel">("single");
  const [carouselSlideIndex, setCarouselSlideIndex] = useState(0);
  const [format, setFormat] = useState<InstagramFormat>("portrait");
  const [themeId, setThemeId] = useState<ThemeId>("verified_brief");
  const [customHeadline, setCustomHeadline] = useState<string>("");
  const [customDek, setCustomDek] = useState<string>("");
  const [customCategory, setCustomCategory] = useState<string>("");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [showPhotoSearch, setShowPhotoSearch] = useState(false);

  useEffect(() => { if (queryEventId) setSelectedEventId(queryEventId); }, [queryEventId]);

  const { data: eventsData } = useQuery({
    queryKey: ["studio_events"],
    queryFn: () => api.listEvents({ limit: 50, sort: "trend_score" }),
  });
  const events = eventsData?.items ?? [];

  const { data: singleEventData } = useQuery({
    queryKey: ["studio_single_event", selectedEventId],
    queryFn: () => api.getEvent(selectedEventId),
    enabled: !!selectedEventId,
  });
  const activeEvent = singleEventData || events.find((e) => e.id === selectedEventId);

  useEffect(() => {
    if (activeEvent) {
      setCustomHeadline(activeEvent.title);
      setCustomDek(activeEvent.summary || "");
      setCustomCategory(activeEvent.primary_category || "News");
    } else {
      setCustomHeadline("");
      setCustomDek("");
      setCustomCategory("");
    }
  }, [activeEvent]);

  const { data: visualAssets = [], refetch: refetchAssets } = useQuery({
    queryKey: ["event_visual_assets", selectedEventId],
    queryFn: () => postsApi.listAssets(selectedEventId),
    enabled: !!selectedEventId,
    refetchInterval: 6000,
  });

  const currentAsset =
    visualAssets.find((a) => a.id === selectedAssetId) ||
    visualAssets.find((a) => a.is_selected) ||
    visualAssets[0];

  const generateVisualMutation = useMutation({
    mutationFn: () => postsApi.generateAsset(selectedEventId),
    onSuccess: () => {
      setTimeout(() => refetchAssets(), 3000);
      setTimeout(() => refetchAssets(), 8000);
      setTimeout(() => refetchAssets(), 15000);
    },
  });

  const fetchRealPhotoMutation = useMutation({
    mutationFn: () => postsApi.fetchArticlePhoto(selectedEventId),
    onSuccess: (data) => {
      if (data?.post_id) {
        setSelectedAssetId(data.post_id);
      }
      queryClient.invalidateQueries({ queryKey: ["event_visual_assets", selectedEventId] });
      refetchAssets();
      setTimeout(() => refetchAssets(), 1200);
    },
  });

  const selectAssetMutation = useMutation({
    mutationFn: (assetId: string) => postsApi.selectAsset(assetId),
    onSuccess: (updatedAsset) => {
      setSelectedAssetId(updatedAsset.id);
      queryClient.invalidateQueries({ queryKey: ["event_visual_assets", selectedEventId] });
    },
  });

  const deleteAssetMutation = useMutation({
    mutationFn: (assetId: string) => postsApi.deleteAsset(assetId),
    onSuccess: (_, deletedId) => {
      if (selectedAssetId === deletedId) {
        setSelectedAssetId(null);
      }
      queryClient.invalidateQueries({ queryKey: ["event_visual_assets", selectedEventId] });
      refetchAssets();
    },
  });

  const composeMutation = useMutation({
    mutationFn: () => postsApi.compose({ event_id: selectedEventId, format, theme: themeId }),
    onSuccess: () => alert("Post composed and enqueued! View it in the Posts queue."),
  });

  const previewData: PostTemplateData = activeEvent
    ? {
        category: customCategory || activeEvent.primary_category || "News",
        headline: customHeadline || activeEvent.title,
        dek: customDek || undefined,
        source: "ETHIOTIMES",
        dateLabel: new Date(activeEvent.created_at)
          .toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" })
          .toUpperCase(),
        theme: themeId,
        accent: THEMES[themeId].accent,
        imageUrl: currentAsset?.storage_url || undefined,
      }
    : { ...SAMPLE, theme: themeId, accent: THEMES[themeId].accent, imageUrl: currentAsset?.storage_url || undefined };

  const carouselSlides: CarouselSlideData[] = [
    { slide_number: 1, total_slides: 5, slide_type: "cover", header: previewData.headline, body_text: previewData.dek, bullet_points: [], source_attribution: previewData.source, accent: THEMES[themeId].accent as "green" | "red" | "gold", imageUrl: currentAsset?.storage_url || undefined },
    { slide_number: 2, total_slides: 5, slide_type: "what_happened", header: "What Happened", body_text: previewData.dek || "Full reporting on recent developments.", bullet_points: [], accent: THEMES[themeId].accent as "green" | "red" | "gold" },
    { slide_number: 3, total_slides: 5, slide_type: "key_facts", header: "Key Verified Facts", bullet_points: ["First documented development confirmed by official release.", "Monitored through multiple independent reporting channels.", "Corroborated by verified field dispatches."], accent: THEMES[themeId].accent as "green" | "red" | "gold" },
    { slide_number: 4, total_slides: 5, slide_type: "why_it_matters", header: "Why It Matters", body_text: "Strategic implications for Ethiopia's economic, political, and institutional framework.", accent: THEMES[themeId].accent as "green" | "red" | "gold" },
    { slide_number: 5, total_slides: 5, slide_type: "sources", header: "Verified Sources", body_text: "Reported and verified across authorized news desks.", bullet_points: [previewData.source || "ETHIOTIMES Intelligence"], source_attribution: previewData.source || "ETHIOTIMES Intelligence", accent: THEMES[themeId].accent as "green" | "red" | "gold" },
  ];

  const isLoadingImage = generateVisualMutation.isPending || fetchRealPhotoMutation.isPending;

  return (
    <>
      {showPhotoSearch && selectedEventId && (
        <PhotoSearchDialog
          eventId={selectedEventId}
          eventTitle={activeEvent?.title}
          eventCategory={activeEvent?.primary_category}
          onClose={() => setShowPhotoSearch(false)}
          onSelect={(assetId) => {
            setSelectedAssetId(assetId);
            queryClient.invalidateQueries({ queryKey: ["event_visual_assets", selectedEventId] });
            refetchAssets();
          }}
        />
      )}
      <PageShell title="Photo & Visual Studio">
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-6">

            {/* Story Selector Card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Palette className="h-4 w-4 text-accent-green" />
                    News Story & Editorial Direction
                  </CardTitle>
                  {activeEvent && (
                    <Badge variant={activeEvent.verification_score >= 75 ? "green" : "gold"}>
                      Score: {activeEvent.verification_score}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-xs uppercase tracking-label text-paper-500 mb-1.5 font-mono">Select News Story</label>
                  <select
                    value={selectedEventId}
                    onChange={(e) => { setSelectedEventId(e.target.value); setSelectedAssetId(null); }}
                    className="w-full h-10 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-50 focus:border-accent-green focus:outline-none"
                  >
                    <option value="">-- Choose an Event ({events.length} available) --</option>
                    {events.map((e) => (
                      <option key={e.id} value={e.id}>
                        [{e.primary_category || "General"}] {e.title.slice(0, 65)}... (Score: {e.verification_score})
                      </option>
                    ))}
                  </select>
                </div>
                {activeEvent && (
                  <div className="space-y-3 pt-2 border-t border-ink-700">
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Headline (Live on Card)</label>
                      <input type="text" value={customHeadline} onChange={(e) => setCustomHeadline(e.target.value)}
                        className="w-full h-9 rounded-card border border-ink-700 bg-ink-800 px-3 text-sm text-paper-100 focus:border-accent-green focus:outline-none font-sans" />
                    </div>
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Dek / Subheading</label>
                      <textarea rows={2} value={customDek} onChange={(e) => setCustomDek(e.target.value)}
                        className="w-full rounded-card border border-ink-700 bg-ink-800 p-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none font-sans resize-none" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Category Pill</label>
                        <input type="text" value={customCategory} onChange={(e) => setCustomCategory(e.target.value)}
                          className="w-full h-8 rounded-card border border-ink-700 bg-ink-800 px-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none" />
                      </div>
                      <div>
                        <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Primary Region</label>
                        <div className="h-8 rounded-card border border-ink-800 bg-ink-900 px-2.5 flex items-center text-xs text-paper-400">
                          {activeEvent.primary_region || "National / Pan-Ethiopia"}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Visual Assets Card with 2-button image sourcing */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <ImageIcon className="h-4 w-4 text-accent-green" />
                    Editorial Visual Assets
                  </CardTitle>
                  <Badge variant="muted" className="font-mono text-[10px]">{visualAssets.length} saved</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">

                {/* PRIMARY 2-BUTTON IMAGE SOURCE ROW */}
                <div className="grid grid-cols-2 gap-3">

                  {/* LEFT: AI Generate button */}
                  <button
                    disabled={!selectedEventId || isLoadingImage}
                    onClick={() => generateVisualMutation.mutate()}
                    className={`flex flex-col items-start gap-2 px-4 py-3.5 rounded-card border-2 transition-all text-left w-full ${
                      generateVisualMutation.isPending
                        ? "border-purple-600 bg-purple-950/30 cursor-wait"
                        : "border-ink-600 hover:border-purple-500 hover:bg-purple-950/20 active:scale-[0.98] cursor-pointer"
                    } ${!selectedEventId ? "opacity-40 cursor-not-allowed" : ""}`}
                  >
                    <div className="flex items-center gap-2">
                      {generateVisualMutation.isPending
                        ? <RefreshCw className="h-4 w-4 animate-spin text-purple-400 shrink-0" />
                        : <Bot className="h-4 w-4 text-purple-400 shrink-0" />
                      }
                      <span className="text-xs font-semibold text-paper-100">
                        {generateVisualMutation.isPending ? "Generating..." : "AI Generate"}
                      </span>
                    </div>
                    <p className="text-[10px] text-paper-500 leading-relaxed">
                      Story-matched image via FLUX. Prompt built from story location, subject & mood.
                    </p>
                    <span className="text-[9px] font-mono text-purple-400 bg-purple-900/30 px-1.5 py-0.5 rounded">
                      ~7-10 sec · Free · FLUX
                    </span>
                  </button>

                  {/* RIGHT: Real photo buttons (stacked) */}
                  <div className="flex flex-col gap-2">
                    <button
                      disabled={!selectedEventId || isLoadingImage}
                      onClick={() => fetchRealPhotoMutation.mutate()}
                      className={`flex items-center gap-2.5 px-3 py-3 rounded-card border-2 transition-all w-full text-left ${
                        fetchRealPhotoMutation.isPending
                          ? "border-emerald-600 bg-emerald-950/30 cursor-wait"
                          : "border-ink-600 hover:border-emerald-500 hover:bg-emerald-950/20 active:scale-[0.98] cursor-pointer"
                      } ${!selectedEventId ? "opacity-40 cursor-not-allowed" : ""}`}
                    >
                      {fetchRealPhotoMutation.isPending
                        ? <RefreshCw className="h-4 w-4 animate-spin text-emerald-400 shrink-0" />
                        : <Newspaper className="h-4 w-4 text-emerald-400 shrink-0" />
                      }
                      <div>
                        <div className="text-xs font-semibold text-paper-100">Article Photo</div>
                        <div className="text-[9px] text-paper-500">From news source feed</div>
                      </div>
                    </button>
                    <button
                      disabled={!selectedEventId || isLoadingImage}
                      onClick={() => setShowPhotoSearch(true)}
                      className={`flex items-center gap-2.5 px-3 py-3 rounded-card border-2 transition-all w-full text-left border-ink-600 hover:border-blue-500 hover:bg-blue-950/20 active:scale-[0.98] cursor-pointer ${!selectedEventId ? "opacity-40 cursor-not-allowed" : ""}`}
                    >
                      <Globe className="h-4 w-4 text-blue-400 shrink-0" />
                      <div>
                        <div className="text-xs font-semibold text-paper-100">Browse Real Photos</div>
                        <div className="text-[9px] text-paper-500">6 editorial alternatives</div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Source legend */}
                <div className="flex items-center gap-4 text-[10px] text-paper-600 font-mono">
                  <span className="flex items-center gap-1"><Camera className="h-2.5 w-2.5 text-emerald-400" /> Real photo</span>
                  <span className="flex items-center gap-1"><Globe className="h-2.5 w-2.5 text-blue-400" /> Pexels</span>
                  <span className="flex items-center gap-1"><Bot className="h-2.5 w-2.5 text-purple-400" /> AI generated</span>
                </div>

                {/* Asset gallery */}
                {!selectedEventId ? (
                  <div className="py-6 text-center text-xs text-paper-500">
                    Select a news event above to view or generate visual imagery.
                  </div>
                ) : visualAssets.length === 0 ? (
                  <div className="py-6 text-center space-y-2 rounded-card border border-dashed border-ink-700 bg-ink-900/50 p-4">
                    <ImageIcon className="mx-auto h-8 w-8 text-paper-600" />
                    <div className="text-xs text-paper-400">No visuals yet — use the buttons above to generate or find photos.</div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-3">
                      {visualAssets.map((asset) => {
                        const isSelected = currentAsset?.id === asset.id || asset.is_selected;
                        return (
                          <div key={asset.id} onClick={() => selectAssetMutation.mutate(asset.id)}
                            className={`group relative cursor-pointer overflow-hidden rounded-card border transition-all ${
                              isSelected
                                ? "border-accent-green ring-2 ring-accent-green/30 bg-ink-800"
                                : "border-ink-700 bg-ink-850 hover:border-ink-500"
                            }`}>
                            <div className="aspect-[4/5] w-full overflow-hidden bg-ink-900 relative">
                              {asset.storage_url
                                // eslint-disable-next-line @next/next/no-img-element
                                ? <img src={asset.storage_url} alt="Visual" className="h-full w-full object-cover transition-transform group-hover:scale-105" />
                                : <div className="h-full w-full flex items-center justify-center"><RefreshCw className="h-4 w-4 animate-spin text-paper-600" /></div>
                              }
                              {isSelected && (
                                <div className="absolute top-1.5 right-1.5 rounded-full bg-accent-green p-0.5 text-ink-900 shadow">
                                  <Check className="h-3 w-3 stroke-[3]" />
                                </div>
                              )}
                              <button
                                type="button"
                                title="Delete image"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (confirm("Delete this visual asset?")) {
                                    deleteAssetMutation.mutate(asset.id);
                                  }
                                }}
                                className="absolute top-1.5 left-1.5 rounded-full bg-ink-950/80 hover:bg-red-900/90 p-1 text-paper-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                            <div className="p-2 space-y-1">
                              <div className="flex items-center justify-between gap-1">
                                <AssetSourceBadge asset={asset} />
                                <span className="text-[9px] text-paper-500 font-mono">{asset.quality_score ?? 80}pts</span>
                              </div>
                              <div className="text-[9px] text-paper-400 truncate leading-tight">{asset.style || "Editorial"}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="text-[11px] text-paper-400 flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-accent-green shrink-0" />
                      Click any thumbnail to select it as the post background.
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Styling Card */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">Card Styling & Typography Themes</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">Post Architecture</label>
                  <div className="flex gap-2">
                    {(["single", "carousel"] as const).map((mode) => (
                      <button key={mode} type="button" onClick={() => setPostMode(mode)}
                        className={`px-3.5 py-2 rounded-card text-xs transition-colors ${
                          postMode === mode
                            ? "bg-accent-green text-ink-900 font-semibold"
                            : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                        }`}>
                        {mode === "single" ? "Single Card Post" : "Multi-Slide Carousel (5 Slides)"}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">Editorial Theme Layout</label>
                  <div className="flex flex-wrap gap-2">
                    {THEME_IDS.map((tid) => (
                      <button key={tid} onClick={() => setThemeId(tid)}
                        className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                          themeId === tid
                            ? "bg-ink-700 text-paper-50 border border-accent-green/60 font-medium"
                            : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                        }`}>
                        {THEMES[tid].label}
                      </button>
                    ))}
                  </div>
                </div>
                {postMode === "single" ? (
                  <div>
                    <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">Instagram Format</label>
                    <div className="flex gap-2">
                      {(Object.keys(FORMATS) as InstagramFormat[]).map((f) => (
                        <button key={f} onClick={() => setFormat(f)}
                          className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                            format === f
                              ? "bg-ink-700 text-paper-50 border border-accent-green/60 font-medium"
                              : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                          }`}>
                          {FORMATS[f].label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">Carousel Slide Navigator</label>
                    <div className="flex flex-wrap gap-2">
                      {carouselSlides.map((s, idx) => (
                        <button key={s.slide_number} onClick={() => setCarouselSlideIndex(idx)}
                          className={`px-3 py-1.5 rounded-card text-xs font-mono transition-colors ${
                            carouselSlideIndex === idx
                              ? "bg-ink-700 text-accent-green border border-accent-green/60 font-semibold"
                              : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                          }`}>
                          {idx + 1}. {s.slide_type.replace("_", " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="pt-2 border-t border-ink-700">
                  <Button disabled={!selectedEventId || composeMutation.isPending} onClick={() => composeMutation.mutate()}
                    className="w-full flex items-center justify-center gap-2 h-10">
                    <Sparkles className="h-4 w-4" />
                    {composeMutation.isPending ? "Queuing Post..." : "Compose Instagram Post"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: Live Preview */}
          <div className="xl:col-span-6 flex flex-col items-center">
            <div className="w-full sticky top-6 space-y-4">
              <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-2 text-xs text-paper-400 font-mono">
                  <span className="inline-block h-2 w-2 rounded-full bg-accent-green animate-pulse" />
                  <span>Live Rendering Canvas (1080x1350)</span>
                </div>
                <Badge variant="muted" className="font-mono text-[10px]">
                  {postMode === "single" ? `${format.toUpperCase()} · ${THEMES[themeId].label}` : `SLIDE ${carouselSlideIndex + 1} OF 5`}
                </Badge>
              </div>
              <div className="flex justify-center bg-ink-950 border border-ink-700 rounded-card p-6 overflow-hidden shadow-inner min-h-[620px] items-center">
                {postMode === "single" ? (
                  <ScaledPreview width={FORMATS[format].width} height={FORMATS[format].height} target={380}>
                    {format === "portrait" && <PortraitPost data={previewData} />}
                    {format === "square" && <SquarePost data={previewData} />}
                    {format === "story" && <StoryPost data={previewData} />}
                  </ScaledPreview>
                ) : (
                  <ScaledPreview width={1080} height={1350} target={380}>
                    <CarouselCard slide={carouselSlides[carouselSlideIndex]} />
                  </ScaledPreview>
                )}
              </div>
              <div className="rounded-card border border-ink-800 bg-ink-900 p-3 text-xs text-paper-400 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ImageIcon className="h-4 w-4 text-accent-green" />
                  <span>Active Visual: <strong className="text-paper-200">{currentAsset ? (currentAsset.style || currentAsset.model || "Custom Photo") : "None (Dark Scrim Only)"}</strong></span>
                  {currentAsset && <AssetSourceBadge asset={currentAsset} />}
                </div>
                {currentAsset?.storage_url && (
                  <a href={currentAsset.storage_url} target="_blank" rel="noopener noreferrer"
                    className="text-accent-green hover:underline text-[11px] font-mono">View Full Res ↗</a>
                )}
              </div>
            </div>
          </div>
        </div>
      </PageShell>
    </>
  );
}

export default function TemplatesStudioPage() {
  return (
    <Suspense fallback={
      <PageShell title="Photo & Visual Studio">
        <div className="py-20 text-center text-sm text-paper-500 flex items-center justify-center gap-2">
          <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
          <span>Loading Photo Studio...</span>
        </div>
      </PageShell>
    }>
      <StudioContent />
    </Suspense>
  );
}
