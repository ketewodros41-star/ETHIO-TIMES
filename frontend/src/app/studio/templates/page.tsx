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
  ImageIcon,
  Sparkles,
  RefreshCw,
  Check,
  Palette,
  CheckCircle2,
} from "lucide-react";
import {
  FORMATS,
  PortraitPost,
  SquarePost,
  StoryPost,
  CarouselCard,
  THEMES,
  THEME_IDS,
  type InstagramFormat,
  type ThemeId,
  type PostTemplateData,
  type CarouselSlideData,
} from "@/templates/instagram";

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

function ScaledPreview({
  width,
  height,
  target,
  children,
}: {
  width: number;
  height: number;
  target: number;
  children: React.ReactNode;
}) {
  const scale = target / width;
  return (
    <div
      style={{ width: target, height: height * scale }}
      className="overflow-hidden rounded-card border border-ink-700 bg-ink-900 shadow-2xl relative"
    >
      <div
        style={{
          transform: `scale(${scale})`,
          transformOrigin: "top left",
          width,
          height,
        }}
      >
        {children}
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

  // Editable text overrides for live preview
  const [customHeadline, setCustomHeadline] = useState<string>("");
  const [customDek, setCustomDek] = useState<string>("");
  const [customCategory, setCustomCategory] = useState<string>("");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  // Sync with query param if it changes
  useEffect(() => {
    if (queryEventId) {
      setSelectedEventId(queryEventId);
    }
  }, [queryEventId]);

  // Fetch all active events
  const { data: eventsData } = useQuery({
    queryKey: ["studio_events"],
    queryFn: () =>
      api.listEvents({
        limit: 50,
        sort: "trend_score",
      }),
  });

  const events = eventsData?.items ?? [];

  // If queryEventId is provided, fetch its detail
  const { data: singleEventData } = useQuery({
    queryKey: ["studio_single_event", selectedEventId],
    queryFn: () => api.getEvent(selectedEventId),
    enabled: !!selectedEventId,
  });

  const activeEvent =
    singleEventData || events.find((e) => e.id === selectedEventId);

  // When active event changes, sync editable fields
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

  // Fetch visual assets for selected event
  const {
    data: visualAssets = [],
    refetch: refetchAssets,
  } = useQuery({
    queryKey: ["event_visual_assets", selectedEventId],
    queryFn: () => postsApi.listAssets(selectedEventId),
    enabled: !!selectedEventId,
    refetchInterval: 6000,
  });

  // Pick the active visual asset
  const currentAsset =
    visualAssets.find((a) => a.id === selectedAssetId) ||
    visualAssets.find((a) => a.is_selected) ||
    visualAssets[0];

  // Generate visual asset mutation
  const generateVisualMutation = useMutation({
    mutationFn: () => postsApi.generateAsset(selectedEventId),
    onSuccess: () => {
      setTimeout(() => refetchAssets(), 2000);
      setTimeout(() => refetchAssets(), 6000);
      setTimeout(() => refetchAssets(), 12000);
    },
  });

  // Select asset mutation
  const selectAssetMutation = useMutation({
    mutationFn: (assetId: string) => postsApi.selectAsset(assetId),
    onSuccess: (updatedAsset) => {
      setSelectedAssetId(updatedAsset.id);
      queryClient.invalidateQueries({ queryKey: ["event_visual_assets", selectedEventId] });
    },
  });

  // Compose post mutation
  const composeMutation = useMutation({
    mutationFn: () =>
      postsApi.compose({ event_id: selectedEventId, format, theme: themeId }),
    onSuccess: () => alert("Post successfully composed and enqueued! View it in the Posts queue."),
  });

  const previewData: PostTemplateData = activeEvent
    ? {
        category: customCategory || activeEvent.primary_category || "News",
        headline: customHeadline || activeEvent.title,
        dek: customDek || undefined,
        source: "ETHIOTIMES",
        dateLabel: new Date(activeEvent.created_at)
          .toLocaleDateString("en-US", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })
          .toUpperCase(),
        theme: themeId,
        accent: THEMES[themeId].accent,
        imageUrl: currentAsset?.storage_url || undefined,
      }
    : {
        ...SAMPLE,
        theme: themeId,
        accent: THEMES[themeId].accent,
        imageUrl: currentAsset?.storage_url || undefined,
      };

  const carouselSlides: CarouselSlideData[] = [
    {
      slide_number: 1,
      total_slides: 5,
      slide_type: "cover",
      header: previewData.headline,
      body_text: previewData.dek,
      bullet_points: [],
      source_attribution: previewData.source,
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      imageUrl: currentAsset?.storage_url || undefined,
    },
    {
      slide_number: 2,
      total_slides: 5,
      slide_type: "what_happened",
      header: "What Happened",
      body_text: previewData.dek || "Full reporting on recent developments.",
      bullet_points: [],
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
    },
    {
      slide_number: 3,
      total_slides: 5,
      slide_type: "key_facts",
      header: "Key Verified Facts",
      bullet_points: [
        "First documented development confirmed by official release.",
        "Monitored through multiple independent reporting channels.",
        "Corroborated by verified field dispatches.",
      ],
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
    },
    {
      slide_number: 4,
      total_slides: 5,
      slide_type: "why_it_matters",
      header: "Why It Matters",
      body_text:
        "Strategic implications for Ethiopia's economic, political, and institutional framework.",
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
    },
    {
      slide_number: 5,
      total_slides: 5,
      slide_type: "sources",
      header: "Verified Sources",
      body_text: "Reported and verified across authorized news desks.",
      bullet_points: [previewData.source || "ETHIOTIMES Intelligence"],
      source_attribution: previewData.source || "ETHIOTIMES Intelligence",
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
    },
  ];

  return (
    <PageShell title="Photo & Visual Studio">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        {/* Left Column: Studio Controls */}
        <div className="space-y-6 xl:col-span-6">
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
              {/* Event Dropdown Selector */}
              <div>
                <label className="block text-xs uppercase tracking-label text-paper-500 mb-1.5 font-mono">
                  Select News Story
                </label>
                <select
                  value={selectedEventId}
                  onChange={(e) => {
                    setSelectedEventId(e.target.value);
                    setSelectedAssetId(null);
                  }}
                  className="w-full h-10 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-50 focus:border-accent-green focus:outline-none"
                >
                  <option value="">-- Choose an Event ({events.length} available) --</option>
                  {events.map((e) => (
                    <option key={e.id} value={e.id}>
                      [{e.primary_category || "General"}] {e.title.slice(0, 65)}… (Score: {e.verification_score})
                    </option>
                  ))}
                </select>
              </div>

              {/* Live Editable Text Fields */}
              {activeEvent && (
                <div className="space-y-3 pt-2 border-t border-ink-700">
                  <div>
                    <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">
                      Headline (Live on Card)
                    </label>
                    <input
                      type="text"
                      value={customHeadline}
                      onChange={(e) => setCustomHeadline(e.target.value)}
                      className="w-full h-9 rounded-card border border-ink-700 bg-ink-800 px-3 text-sm text-paper-100 focus:border-accent-green focus:outline-none font-sans"
                    />
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">
                      Dek / Subheading (Live on Card)
                    </label>
                    <textarea
                      rows={2}
                      value={customDek}
                      onChange={(e) => setCustomDek(e.target.value)}
                      className="w-full rounded-card border border-ink-700 bg-ink-800 p-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none font-sans resize-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">
                        Category Pill
                      </label>
                      <input
                        type="text"
                        value={customCategory}
                        onChange={(e) => setCustomCategory(e.target.value)}
                        className="w-full h-8 rounded-card border border-ink-700 bg-ink-800 px-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">
                        Primary Region
                      </label>
                      <div className="h-8 rounded-card border border-ink-800 bg-ink-900 px-2.5 flex items-center text-xs text-paper-400">
                        {activeEvent.primary_region || "National / Pan-Ethiopia"}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* AI Visual Interpretation & Photos */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <ImageIcon className="h-4 w-4 text-accent-green" />
                  Editorial Visual Assets
                </CardTitle>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!selectedEventId || generateVisualMutation.isPending}
                  onClick={() => generateVisualMutation.mutate()}
                  className="flex items-center gap-1.5 h-8 text-xs border-ink-600 hover:border-accent-green"
                >
                  {generateVisualMutation.isPending ? (
                    <>
                      <RefreshCw className="h-3 w-3 animate-spin text-accent-green" />
                      Generating AI Imagery…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3 w-3 text-accent-green" />
                      Generate Visual Interpretation
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!selectedEventId ? (
                <div className="py-6 text-center text-xs text-paper-500">
                  Select a news event above to view or generate visual imagery.
                </div>
              ) : visualAssets.length === 0 ? (
                <div className="py-6 text-center space-y-3 rounded-card border border-dashed border-ink-700 bg-ink-900/50 p-4">
                  <ImageIcon className="mx-auto h-8 w-8 text-paper-600" />
                  <div className="text-xs text-paper-400">
                    No visual asset generated yet for this story.
                  </div>
                  <Button
                    size="sm"
                    disabled={generateVisualMutation.isPending}
                    onClick={() => generateVisualMutation.mutate()}
                    className="flex items-center gap-1.5 mx-auto text-xs"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {generateVisualMutation.isPending ? "Generating Imagery…" : "Generate First Visual"}
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    {visualAssets.map((asset) => {
                      const isSelected =
                        currentAsset?.id === asset.id || asset.is_selected;
                      return (
                        <div
                          key={asset.id}
                          onClick={() => selectAssetMutation.mutate(asset.id)}
                          className={`group relative cursor-pointer overflow-hidden rounded-card border transition-all ${
                            isSelected
                              ? "border-accent-green ring-2 ring-accent-green/30 bg-ink-800"
                              : "border-ink-700 bg-ink-850 hover:border-ink-500"
                          }`}
                        >
                          <div className="aspect-[4/5] w-full overflow-hidden bg-ink-900 relative">
                            {asset.storage_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={asset.storage_url}
                                alt="Visual candidate"
                                className="h-full w-full object-cover transition-transform group-hover:scale-105"
                              />
                            ) : (
                              <div className="h-full w-full flex items-center justify-center text-xs text-paper-600">
                                Generating…
                              </div>
                            )}
                            {isSelected && (
                              <div className="absolute top-1.5 right-1.5 rounded-full bg-accent-green p-0.5 text-ink-900 shadow">
                                <Check className="h-3 w-3 stroke-[3]" />
                              </div>
                            )}
                          </div>
                          <div className="p-2 text-[10px]">
                            <div className="font-semibold text-paper-200 truncate">
                              {asset.style || "Editorial"}
                            </div>
                            <div className="flex items-center justify-between text-paper-500 font-mono mt-0.5">
                              <span>Score: {asset.quality_score ?? 80}</span>
                              <span className="capitalize">{asset.status}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-[11px] text-paper-400 flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-accent-green shrink-0" />
                    Click any thumbnail above to select it as the background for this Instagram post card.
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Publishing Mode, Theme & Format */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">
                Card Styling & Typography Themes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Post Mode Toggle */}
              <div>
                <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">
                  Post Architecture
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setPostMode("single")}
                    className={`px-3.5 py-2 rounded-card text-xs transition-colors ${
                      postMode === "single"
                        ? "bg-accent-green text-ink-900 font-semibold"
                        : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                    }`}
                  >
                    Single Card Post
                  </button>
                  <button
                    type="button"
                    onClick={() => setPostMode("carousel")}
                    className={`px-3.5 py-2 rounded-card text-xs transition-colors ${
                      postMode === "carousel"
                        ? "bg-accent-green text-ink-900 font-semibold"
                        : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                    }`}
                  >
                    Multi-Slide Carousel (5 Slides)
                  </button>
                </div>
              </div>

              {/* Theme Selector */}
              <div>
                <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">
                  Editorial Theme Layout
                </label>
                <div className="flex flex-wrap gap-2">
                  {THEME_IDS.map((tid) => (
                    <button
                      key={tid}
                      onClick={() => setThemeId(tid)}
                      className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                        themeId === tid
                          ? "bg-ink-700 text-paper-50 border border-accent-green/60 font-medium"
                          : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                      }`}
                    >
                      {THEMES[tid].label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Format or Carousel Nav */}
              {postMode === "single" ? (
                <div>
                  <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">
                    Instagram Format
                  </label>
                  <div className="flex gap-2">
                    {(Object.keys(FORMATS) as InstagramFormat[]).map((f) => (
                      <button
                        key={f}
                        onClick={() => setFormat(f)}
                        className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                          format === f
                            ? "bg-ink-700 text-paper-50 border border-accent-green/60 font-medium"
                            : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                        }`}
                      >
                        {FORMATS[f].label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-xs uppercase tracking-label text-paper-500 mb-2 font-mono">
                    Carousel Slide Navigator
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {carouselSlides.map((s, idx) => (
                      <button
                        key={s.slide_number}
                        onClick={() => setCarouselSlideIndex(idx)}
                        className={`px-3 py-1.5 rounded-card text-xs font-mono transition-colors ${
                          carouselSlideIndex === idx
                            ? "bg-ink-700 text-accent-green border border-accent-green/60 font-semibold"
                            : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                        }`}
                      >
                        {idx + 1}. {s.slide_type.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Compose Action */}
              <div className="pt-2 border-t border-ink-700">
                <Button
                  disabled={!selectedEventId || composeMutation.isPending}
                  onClick={() => composeMutation.mutate()}
                  className="w-full flex items-center justify-center gap-2 h-10"
                >
                  <Sparkles className="h-4 w-4" />
                  {composeMutation.isPending ? "Queuing Post…" : "Compose Instagram Post"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Live Scaled True-Pixel Post Preview */}
        <div className="xl:col-span-6 flex flex-col items-center">
          <div className="w-full sticky top-6 space-y-4">
            <div className="flex items-center justify-between px-2">
              <div className="flex items-center gap-2 text-xs text-paper-400 font-mono">
                <span className="inline-block h-2 w-2 rounded-full bg-accent-green animate-pulse" />
                <span>Live Rendering Canvas (1080×1350)</span>
              </div>
              <Badge variant="muted" className="font-mono text-[10px]">
                {postMode === "single" ? `${format.toUpperCase()} · ${THEMES[themeId].label}` : `SLIDE ${carouselSlideIndex + 1} OF 5`}
              </Badge>
            </div>

            <div className="flex justify-center bg-ink-950 border border-ink-700 rounded-card p-6 overflow-hidden shadow-inner min-h-[620px] items-center">
              {postMode === "single" ? (
                <ScaledPreview
                  width={FORMATS[format].width}
                  height={FORMATS[format].height}
                  target={380}
                >
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

            {/* Visual Asset info banner */}
            <div className="rounded-card border border-ink-800 bg-ink-900 p-3 text-xs text-paper-400 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4 text-accent-green" />
                <span>Active Visual: <strong className="text-paper-200">{currentAsset ? (currentAsset.style || currentAsset.model || "Custom Photo") : "None (Dark Scrim Only)"}</strong></span>
              </div>
              {currentAsset?.storage_url && (
                <a
                  href={currentAsset.storage_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-green hover:underline text-[11px] font-mono"
                >
                  View Full Res ↗
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}

export default function TemplatesStudioPage() {
  return (
    <Suspense
      fallback={
        <PageShell title="Photo & Visual Studio">
          <div className="py-20 text-center text-sm text-paper-500 flex items-center justify-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin text-accent-green" />
            <span>Loading Photo Studio…</span>
          </div>
        </PageShell>
      }
    >
      <StudioContent />
    </Suspense>
  );
}
