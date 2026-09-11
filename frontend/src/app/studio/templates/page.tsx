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
  Maximize2, ZoomIn, ZoomOut, MapPin, Building2, Languages,
} from "lucide-react";
import {
  FORMATS, PortraitPost, SquarePost, StoryPost, CarouselCard,
  THEMES, THEME_IDS,
  type InstagramFormat, type ThemeId, type PostTemplateData, type CarouselSlideData,
} from "@/templates/instagram";
import { isEthiopic } from "@/templates/instagram/primitives";
import { HIGHLIGHT_PALETTES, type HighlightColorToken } from "@/lib/design-tokens";
import { parseHeadlineSegments, type HighlightMode } from "@/templates/instagram/headline-highlighter";
import { POPULAR_COUNTRIES, resolveCountryCode } from "@/components/country-flag";
import type { VisualAsset, PhotoCandidate } from "@/lib/types";

const SAMPLE: PostTemplateData = {
  category: "Economy",
  headline: "National Bank signals shift as birr reforms take hold",
  dek: "Policymakers weigh the next phase of Ethiopia's macroeconomic overhaul amid cooling inflation.",
  source: "Addis Fortune",
  dateLabel: "9 SEP 2026",
  accent: "green",
  style: "Premium Magazine",
  theme: "broadcast_impact",
  highlightColor: "#00F0FF",
  highlightMode: "auto",
};

const AMHARIC_PRESETS = [
  {
    key: "mbappe",
    label: "⚽ ምባፔ እና ማን ዩናይትድ",
    category: "ስፖርት",
    headline: "ማንቸስተር ዩናይትድ ኪሊያን ምባፔን ሊያስፈርም ነበር",
    dek: "ዩናይትድ በታዳጊነቱ ሊያስፈርመው ይችል እንደነበር ራያን ጊግስ ይፋ አደረገ።",
    highlightColor: "#D4FF00",
    highlightMode: "auto" as HighlightMode,
    country: "United Kingdom",
  },
  {
    key: "economy",
    label: "📈 የብር ምንዛሪ ማሻሻያ",
    category: "ኢኮኖሚ",
    headline: "ብሔራዊ ባንክ የውጭ ምንዛሪ አሠራርን አሻሻለ",
    dek: "የኢኮኖሚ ማሻሻያውን ተከትሎ የዋጋ ግሽበት እያሽቆለቆለ መምጣቱ ተገለጸ።",
    highlightColor: "#FFB800",
    highlightMode: "auto" as HighlightMode,
    country: "Ethiopia",
  },
  {
    key: "breaking",
    label: "🚨 ሰበር የትራንስፖርት ታሪፍ",
    category: "ሰበር ዜና",
    headline: "በአዲስ አበባ አዲስ የትራንስፖርት ታሪፍ ወጣ",
    dek: "ከነገ ጀምሮ በሁሉም የከተማዋ መስመሮች አዲሱ የታሪፍ ማስተካከያ ተግባራዊ ይሆናል።",
    highlightColor: "#FF385C",
    highlightMode: "auto" as HighlightMode,
    country: "Ethiopia",
  },
  {
    key: "tech",
    label: "🤖 አርቴፊሻል ኢንተለጀንስ",
    category: "ቴክኖሎጂ",
    headline: "ኢትዮጵያ አርቴፊሻል ኢንተለጀንስን ልታሰማራ ነው",
    dek: "በግብርና እና ጤና ዘርፍ ምርታማነትን ለማሳደግ አዲስ ሥርዓት ይዘረጋል።",
    highlightColor: "#00F5A0",
    highlightMode: "auto" as HighlightMode,
    country: "Ethiopia",
  },
];

function ScaledPreview({ width, height, target, children }: {
  width: number; height: number; target: number; children: React.ReactNode;
}) {
  const scale = target / width;
  return (
    <div style={{ width: target, height: height * scale }}
      className="overflow-hidden rounded-card border border-ink-700 bg-ink-900 shadow-2xl relative">
      <div style={{
        transform: `translate3d(0, 0, 0) scale(${scale})`,
        transformOrigin: "top left",
        width,
        height,
        imageRendering: "-webkit-optimize-contrast",
        WebkitFontSmoothing: "antialiased",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        willChange: "transform",
      }}>
        {children}
      </div>
    </div>
  );
}

function InspectorModal({
  children,
  width,
  height,
  zoom,
  onZoomChange,
  onClose,
  headerExtras,
}: {
  children: React.ReactNode;
  width: number;
  height: number;
  zoom: number;
  onZoomChange: (z: number) => void;
  onClose: () => void;
  headerExtras?: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink-950/95 backdrop-blur-md animate-in fade-in duration-150">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-ink-800 px-6 py-3 bg-ink-900">
        <div className="flex items-center gap-3">
          <span className="flex h-2.5 w-2.5 rounded-full bg-accent-green animate-pulse" />
          <h2 className="text-sm font-semibold text-paper-100 font-mono">
            4K UHD Master Inspector ({width} × {height}px)
          </h2>
          <span className="text-xs text-paper-400 hidden sm:inline">
            Evaluating true 1:1 pixel rendering, typography sharpness & photo textures
          </span>
        </div>
        <div className="flex items-center gap-3">
          {headerExtras}
          <div className="flex items-center gap-1 bg-ink-950 border border-ink-700 rounded-lg p-1 text-xs">
            <button
              onClick={() => onZoomChange(Math.max(0.4, Number((zoom - 0.15).toFixed(2))))}
              className="p-1 rounded hover:bg-ink-800 text-paper-300 hover:text-paper-100"
              title="Zoom out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <span className="px-2 font-mono text-accent-green min-w-[52px] text-center font-bold">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => onZoomChange(Math.min(2.0, Number((zoom + 0.15).toFixed(2))))}
              className="p-1 rounded hover:bg-ink-800 text-paper-300 hover:text-paper-100"
              title="Zoom in"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => onZoomChange(1.0)}
              className="px-2 py-0.5 rounded text-[10px] bg-ink-800 hover:bg-ink-700 text-paper-300 font-medium ml-1"
            >
              100% 1:1
            </button>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0 text-paper-400 hover:text-paper-100">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Viewport */}
      <div className="flex-1 overflow-auto p-8 flex items-center justify-center">
        <div
          style={{
            width: width * zoom,
            height: height * zoom,
            transition: "width 0.15s ease-out, height 0.15s ease-out",
          }}
          className="relative shadow-2xl rounded-card overflow-hidden border border-ink-700 bg-ink-900"
        >
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
              width,
              height,
              imageRendering: "-webkit-optimize-contrast",
              WebkitFontSmoothing: "antialiased",
            }}
          >
            {children}
          </div>
        </div>
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
  const [detectedCountry, setDetectedCountry] = useState<string | null>(null);
  const [detectedCountryCode, setDetectedCountryCode] = useState<string | null>(null);
  const [detectedPerson, setDetectedPerson] = useState<string | null>(null);
  const [detectedPersons, setDetectedPersons] = useState<string[]>([]);
  const [detectedLocations, setDetectedLocations] = useState<string[]>([]);
  const [detectedInstitutions, setDetectedInstitutions] = useState<string[]>([]);
  const [suggestedChips, setSuggestedChips] = useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
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
      if (res.detected_country) setDetectedCountry(res.detected_country);
      if (res.detected_country_code) setDetectedCountryCode(res.detected_country_code);
      if (res.detected_person) setDetectedPerson(res.detected_person);
      if (res.detected_persons) setDetectedPersons(res.detected_persons);
      if (res.detected_locations) setDetectedLocations(res.detected_locations);
      if (res.detected_institutions) setDetectedInstitutions(res.detected_institutions);
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

  const categoryCounts = {
    all: results.length,
    lead: results.filter((r) => r.entity_type === "lead").length,
    person: results.filter((r) => r.entity_type === "person").length,
    location: results.filter((r) => r.entity_type === "location").length,
    institution: results.filter((r) => r.entity_type === "institution").length,
  };

  const displayedResults =
    categoryFilter === "all"
      ? results
      : results.filter((r) => r.entity_type === categoryFilter);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl bg-ink-900 border border-ink-700 rounded-card shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700">
          <div className="flex items-center gap-2.5">
            <Globe className="h-5 w-5 text-accent-green shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-base text-paper-100">
                  Topic-Based Internet Photo Browsing
                </span>
                <Badge variant="green" className="text-[10px] font-mono">
                  6 per page &bull; Entity Cascade
                </Badge>
                {totalItems > 0 && (
                  <Badge variant="muted" className="text-[10px] font-mono text-paper-400">
                    {totalItems} Available
                  </Badge>
                )}
              </div>
              <p className="text-xs text-paper-400 mt-0.5 truncate max-w-xl">
                {eventTitle ? (
                  <span>
                    Story: <strong className="text-paper-200 font-medium">&ldquo;{eventTitle}&rdquo;</strong>
                  </span>
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
          <div className="flex items-center gap-2 text-xs flex-wrap">
            <Sparkles className="h-4 w-4 text-accent-green shrink-0 animate-pulse" />
            <span className="text-paper-400">Story Topic:</span>
            <strong className="text-accent-green font-medium">
              {topic ? `"${topic}"` : "Extracting article topic & key entities..."}
            </strong>
            {detectedCountry && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-900/60 text-blue-200 border border-blue-700/50">
                <Globe className="h-2.5 w-2.5 shrink-0" />
                <span>{detectedCountry}</span>
              </span>
            )}
            {detectedPersons.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-900/60 text-purple-200 border border-purple-700/50">
                <User className="h-2.5 w-2.5 shrink-0" />
                <span>{detectedPersons.join(", ")}</span>
              </span>
            )}
            {detectedLocations.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-900/60 text-emerald-200 border border-emerald-700/50">
                <MapPin className="h-2.5 w-2.5 shrink-0" />
                <span>{detectedLocations.join(", ")}</span>
              </span>
            )}
            {detectedInstitutions.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-cyan-900/60 text-cyan-200 border border-cyan-700/50">
                <Building2 className="h-2.5 w-2.5 shrink-0" />
                <span>{detectedInstitutions.join(", ")}</span>
              </span>
            )}
          </div>
          {topic && (
            <span className="text-[10px] font-mono text-paper-400">
              4-Tier Waterfall Search &bull; Zero typing needed
            </span>
          )}
        </div>

        {/* Search Bar & Entity Chips */}
        <div className="px-6 py-3 border-b border-ink-800 bg-ink-950/50 space-y-2.5">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch(1, query)}
              placeholder={topic ? `Filtered by story: "${topic}". Or type custom query...` : "Search photos by entity or topic..."}
              className="flex-1 h-9 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-100 focus:border-accent-green focus:outline-none placeholder:text-paper-600"
            />
            <Button
              size="sm"
              disabled={searching || !!importingId}
              onClick={() => handleSearch(1, query)}
              className="h-9 px-4 bg-accent-green text-ink-950 font-semibold hover:bg-accent-green/90 flex items-center gap-1.5"
            >
              {searching ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              {searching ? "Searching..." : "Search"}
            </Button>
            {query && (
              <Button
                size="sm"
                variant="outline"
                disabled={searching}
                onClick={() => {
                  setQuery("");
                  handleSearch(1, "");
                }}
                className="h-9 px-3 border-ink-700 text-paper-400 hover:text-paper-100 text-xs"
              >
                Reset to Story
              </Button>
            )}
          </div>

          {/* Clickable Entity Quick-Chips */}
          {(detectedPersons.length > 0 || detectedLocations.length > 0 || detectedInstitutions.length > 0 || suggestedChips.length > 0) && (
            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
              <span className="text-[10px] text-paper-500 font-mono">Quick entity search:</span>
              {detectedPersons.map((person) => (
                <button
                  key={`person-${person}`}
                  type="button"
                  disabled={searching || !!importingId}
                  onClick={() => {
                    setQuery(person);
                    handleSearch(1, person);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-colors border ${
                    query.toLowerCase() === person.toLowerCase()
                      ? "bg-purple-900/60 border-purple-500 text-purple-200 font-medium"
                      : "bg-purple-950/30 hover:bg-purple-900/40 border-purple-800/60 text-purple-300 hover:text-purple-100"
                  }`}
                  title={`Search for portraits of ${person}`}
                >
                  <User className="h-2.5 w-2.5" />
                  <span>{person}</span>
                </button>
              ))}
              {detectedLocations.map((loc) => (
                <button
                  key={`loc-${loc}`}
                  type="button"
                  disabled={searching || !!importingId}
                  onClick={() => {
                    setQuery(loc);
                    handleSearch(1, loc);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-colors border ${
                    query.toLowerCase() === loc.toLowerCase()
                      ? "bg-emerald-900/60 border-emerald-500 text-emerald-200 font-medium"
                      : "bg-emerald-950/30 hover:bg-emerald-900/40 border-emerald-800/60 text-emerald-300 hover:text-emerald-100"
                  }`}
                  title={`Search for photos of ${loc}`}
                >
                  <MapPin className="h-2.5 w-2.5" />
                  <span>{loc}</span>
                </button>
              ))}
              {detectedInstitutions.map((inst) => (
                <button
                  key={`inst-${inst}`}
                  type="button"
                  disabled={searching || !!importingId}
                  onClick={() => {
                    setQuery(inst);
                    handleSearch(1, inst);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-colors border ${
                    query.toLowerCase() === inst.toLowerCase()
                      ? "bg-cyan-900/60 border-cyan-500 text-cyan-200 font-medium"
                      : "bg-cyan-950/30 hover:bg-cyan-900/40 border-cyan-800/60 text-cyan-300 hover:text-cyan-100"
                  }`}
                  title={`Search for photos of ${inst}`}
                >
                  <Building2 className="h-2.5 w-2.5" />
                  <span>{inst}</span>
                </button>
              ))}
              {suggestedChips
                .filter(
                  (c) =>
                    !detectedPersons.some((p) => p.toLowerCase() === c.toLowerCase()) &&
                    !detectedLocations.some((l) => l.toLowerCase() === c.toLowerCase()) &&
                    !detectedInstitutions.some((i) => i.toLowerCase() === c.toLowerCase())
                )
                .map((chip) => (
                  <button
                    key={`chip-${chip}`}
                    type="button"
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

          {/* Category Filter Tabs */}
          <div className="flex items-center gap-1 pt-1 overflow-x-auto text-xs border-t border-ink-800/80">
            <span className="text-[10px] text-paper-500 font-mono mr-1">Filter Page:</span>
            <button
              type="button"
              onClick={() => setCategoryFilter("all")}
              className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-medium ${
                categoryFilter === "all"
                  ? "bg-accent-green text-ink-950 font-bold"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border border-ink-700"
              }`}
            >
              <Sparkles className="h-3 w-3" />
              <span>All Story-Matched</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                categoryFilter === "all" ? "bg-ink-950/30 text-ink-950" : "bg-ink-800 text-paper-400"
              }`}>
                {categoryCounts.all}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter("lead")}
              className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-medium ${
                categoryFilter === "lead"
                  ? "bg-blue-600 text-white font-bold"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border border-ink-700"
              }`}
            >
              <Newspaper className="h-3 w-3" />
              <span>Lead Photos</span>
              {categoryCounts.lead > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  categoryFilter === "lead" ? "bg-black/30 text-white" : "bg-ink-800 text-paper-400"
                }`}>
                  {categoryCounts.lead}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter("person")}
              className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-medium ${
                categoryFilter === "person"
                  ? "bg-purple-600 text-white font-bold"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border border-ink-700"
              }`}
            >
              <User className="h-3 w-3" />
              <span>Key People</span>
              {categoryCounts.person > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  categoryFilter === "person" ? "bg-black/30 text-white" : "bg-ink-800 text-paper-400"
                }`}>
                  {categoryCounts.person}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter("location")}
              className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-medium ${
                categoryFilter === "location"
                  ? "bg-emerald-600 text-white font-bold"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border border-ink-700"
              }`}
            >
              <MapPin className="h-3 w-3" />
              <span>City & Location</span>
              {categoryCounts.location > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  categoryFilter === "location" ? "bg-black/30 text-white" : "bg-ink-800 text-paper-400"
                }`}>
                  {categoryCounts.location}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter("institution")}
              className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-medium ${
                categoryFilter === "institution"
                  ? "bg-cyan-600 text-white font-bold"
                  : "bg-ink-850 hover:bg-ink-800 text-paper-300 hover:text-paper-100 border border-ink-700"
              }`}
            >
              <Building2 className="h-3 w-3" />
              <span>Institutions</span>
              {categoryCounts.institution > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  categoryFilter === "institution" ? "bg-black/30 text-white" : "bg-ink-800 text-paper-400"
                }`}>
                  {categoryCounts.institution}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Results Body */}
        <div className="px-6 py-4 overflow-y-auto flex-1">
          {errorMsg && (
            <div className="mb-4 p-3 rounded-card bg-red-950/40 border border-red-800/60 text-xs text-red-300">
              {errorMsg}
            </div>
          )}

          {searching && (
            <div className="py-16 text-center space-y-3">
              <RefreshCw className="h-8 w-8 animate-spin text-accent-green mx-auto" />
              <p className="text-sm text-paper-300 font-medium">Searching internet for 6 topic-matched alternatives...</p>
              <p className="text-xs text-paper-500 font-mono">Querying Wikipedia portraits, city archives, and editorial databases</p>
            </div>
          )}

          {!searching && searched && results.length === 0 && (
            <div className="py-16 text-center space-y-3">
              <Globe className="h-10 w-10 text-paper-700 mx-auto" />
              <p className="text-sm text-paper-300">No matching photos found on the web.</p>
              <p className="text-xs text-paper-500">Try clicking one of the suggested entity chips above.</p>
            </div>
          )}

          {!searching && results.length > 0 && displayedResults.length === 0 && (
            <div className="py-12 text-center space-y-2 rounded-card border border-dashed border-ink-700 bg-ink-900/40 p-6">
              <p className="text-xs text-paper-300 font-medium">
                No photos classified under &ldquo;{categoryFilter}&rdquo; on Page {page}.
              </p>
              <p className="text-[11px] text-paper-500">
                Check other pages (total {totalPages} pages) or switch back to &ldquo;All Story-Matched&rdquo;.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCategoryFilter("all")}
                className="mt-2 text-xs border-ink-600 text-accent-green hover:bg-accent-green/10"
              >
                Show All {results.length} Photos on Page {page}
              </Button>
            </div>
          )}

          {!searching && displayedResults.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-paper-400 font-mono">
                <span>
                  Showing {displayedResults.length} of {totalItems} alternatives (Page {page} of {totalPages}):
                </span>
                <span className="text-[11px] text-accent-green font-semibold">Select 1 photo to import to Studio</span>
              </div>
              <div className="grid grid-cols-3 gap-3.5">
                {displayedResults.map((c) => {
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

                        {/* Top Badges Row: Source on Left, Entity Context on Right */}
                        <div className="absolute top-2 left-2 right-2 flex items-center justify-between gap-1 pointer-events-none">
                          <span
                            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border backdrop-blur-md shadow-sm ${
                              c.source === "telegram"
                                ? "bg-blue-900/80 text-blue-200 border-blue-600/60"
                                : c.source === "article" || c.source === "article_source"
                                ? "bg-emerald-900/80 text-emerald-200 border-emerald-600/60"
                                : c.source === "pexels"
                                ? "bg-indigo-900/80 text-indigo-200 border-indigo-600/60"
                                : "bg-amber-900/80 text-amber-200 border-amber-600/60"
                            }`}
                          >
                            {c.source === "telegram"
                              ? "Telegram"
                              : c.source === "article" || c.source === "article_source"
                              ? "Article Lead"
                              : c.source === "pexels"
                              ? "Pexels"
                              : "Wikimedia"}
                          </span>

                          {/* Entity Context Badge */}
                          {c.entity_type === "person" && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-purple-950/90 text-purple-200 border border-purple-600/70 backdrop-blur-md max-w-[125px] truncate shadow-sm">
                              <User className="h-2.5 w-2.5 shrink-0" />
                              <span className="truncate">{c.entity_name || "Portrait"}</span>
                            </span>
                          )}
                          {c.entity_type === "location" && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-emerald-950/90 text-emerald-200 border border-emerald-600/70 backdrop-blur-md max-w-[125px] truncate shadow-sm">
                              <MapPin className="h-2.5 w-2.5 shrink-0" />
                              <span className="truncate">{c.entity_name || "Location"}</span>
                            </span>
                          )}
                          {c.entity_type === "institution" && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-cyan-950/90 text-cyan-200 border border-cyan-600/70 backdrop-blur-md max-w-[125px] truncate shadow-sm">
                              <Building2 className="h-2.5 w-2.5 shrink-0" />
                              <span className="truncate">{c.entity_name || "Institution"}</span>
                            </span>
                          )}
                          {c.entity_type === "lead" && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-950/90 text-blue-200 border border-blue-600/70 backdrop-blur-md shadow-sm">
                              <Newspaper className="h-2.5 w-2.5 shrink-0" />
                              <span>Lead Photo</span>
                            </span>
                          )}
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

        {/* Footer Pagination */}
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
  const [selectedLanguage, setSelectedLanguage] = useState<"en" | "am">("en");
  const [postMode, setPostMode] = useState<"single" | "carousel">("single");
  const [carouselSlideIndex, setCarouselSlideIndex] = useState(0);
  const [format, setFormat] = useState<InstagramFormat>("portrait");
  const [themeId, setThemeId] = useState<ThemeId>("broadcast_impact");
  const [highlightColor, setHighlightColor] = useState<string>("#00F0FF");
  const [highlightMode, setHighlightMode] = useState<HighlightMode>("auto");
  const [manualHighlightIndices, setManualHighlightIndices] = useState<number[]>([]);
  const [customHexInput, setCustomHexInput] = useState<string>("");
  const [selectedCountry, setSelectedCountry] = useState<string>("Ethiopia");
  const [customHeadline, setCustomHeadline] = useState<string>("");
  const [customDek, setCustomDek] = useState<string>("");
  const [customCategory, setCustomCategory] = useState<string>("");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [showPhotoSearch, setShowPhotoSearch] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<number>(380);
  const [carouselViewMode, setCarouselViewMode] = useState<"deck" | "single">("deck");
  const [slideCustomHeaders, setSlideCustomHeaders] = useState<Record<number, string>>({});
  const [slideCustomBodies, setSlideCustomBodies] = useState<Record<number, string>>({});
  const [showInspector, setShowInspector] = useState(false);
  const [inspectorZoom, setInspectorZoom] = useState<number>(1.0);

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
      setManualHighlightIndices([]);
      // Intelligently auto-detect country from event title, region, summary
      const textToScan = `${activeEvent.title} ${activeEvent.primary_region || ""} ${activeEvent.summary || ""}`;
      const code = resolveCountryCode(textToScan);
      const matched = POPULAR_COUNTRIES.find((c) => c.code === code);
      if (matched) {
        setSelectedCountry(matched.label);
      }
    } else {
      setCustomHeadline("");
      setCustomDek("");
      setCustomCategory("");
      setManualHighlightIndices([]);
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

  const isAmharicScript = isEthiopic(customHeadline) || isEthiopic(customDek) || selectedLanguage === "am";

  const previewData: PostTemplateData = activeEvent
    ? {
        category: customCategory || activeEvent.primary_category || (isAmharicScript ? "ዜና" : "News"),
        headline: customHeadline || activeEvent.title,
        dek: customDek || undefined,
        source: "ETHIOPIAN TIMES",
        dateLabel: new Date(activeEvent.created_at)
          .toLocaleDateString(isAmharicScript ? "am-ET" : "en-US", { day: "numeric", month: "short", year: "numeric" })
          .toUpperCase(),
        theme: themeId,
        accent: THEMES[themeId].accent,
        highlightColor,
        highlightMode,
        highlightIndices: manualHighlightIndices.length > 0 ? manualHighlightIndices : undefined,
        country: selectedCountry,
        imageUrl: currentAsset?.storage_url || undefined,
      }
    : {
        ...SAMPLE,
        category: customCategory || (isAmharicScript ? "ኢኮኖሚ" : SAMPLE.category),
        headline: customHeadline || SAMPLE.headline,
        dek: customDek || SAMPLE.dek,
        theme: themeId,
        accent: THEMES[themeId].accent,
        highlightColor,
        highlightMode,
        highlightIndices: manualHighlightIndices.length > 0 ? manualHighlightIndices : undefined,
        country: selectedCountry,
        imageUrl: currentAsset?.storage_url || undefined,
      };

  const currentHeadlineText = customHeadline || (activeEvent?.title ?? SAMPLE.headline);
  const parsedHeadlineInfo = parseHeadlineSegments(currentHeadlineText, {
    mode: highlightMode,
    customIndices: manualHighlightIndices.length > 0 ? manualHighlightIndices : undefined,
  });

  // Generate short, punchy copy for 5-page broadcast carousel
  const rawDek = customDek || (activeEvent?.summary ? activeEvent.summary.split(/[.!?]/)[0] + "." : previewData.dek) || (isAmharicScript ? "ቁልፍ የፖሊሲ መመሪያ ወዲያውኑ ተግባራዊ እንዲሆን ተወሰነ።" : "Key policy directive issued with immediate regional enforcement.");
  const shortFact = rawDek.length > 115 ? rawDek.slice(0, 110).trim() + "..." : rawDek;

  // Extract short 10-12 word claims for Slide 3
  const eventClaims = (activeEvent as any)?.claims as any[] | undefined;
  let shortBullets: string[] = [];
  if (eventClaims && eventClaims.length > 0) {
    shortBullets = eventClaims.slice(0, 3).map((c) => {
      const text = (c.claim_text || "").trim();
      const firstClause = text.split(/[,;.]/)[0]?.trim() || text;
      return firstClause.length > 68 ? firstClause.slice(0, 65).trim() + "..." : firstClause;
    });
  }
  if (shortBullets.length === 0) {
    shortBullets = isAmharicScript
      ? [
          "መመሪያው ወዲያውኑ በሁሉም ዘርፎች ተግባራዊ መሆን ይጀምራል።",
          "የቁጥጥር ቡድኖች በዋና ዋና የንግድ ማዕከላት ተሰማርተዋል።",
          "የአፈጻጸም ሂደቱ በየጊዜው ክትትል እንደሚደረግበት ተገልጿል።",
        ]
      : [
          "Directive takes immediate effect under ministry supervision.",
          "Applies directly across key commerce and retail sectors.",
          "Field teams deployed to verify compliance and stability.",
        ];
  }

  const shortWhy = isAmharicScript
    ? "ውሳኔው በገበያ መረጋጋት እና በቀጣይ የኢኮኖሚ እንቅስቃሴዎች ላይ ከፍተኛ አዎንታዊ ተጽዕኖ ይኖረዋል።"
    : "Critical implications for regional trade dynamics, bilateral market ties, and ongoing economic reforms.";

  const carouselSlides: CarouselSlideData[] = [
    {
      slide_number: 1,
      total_slides: 5,
      slide_type: "cover",
      header: slideCustomHeaders[1] || previewData.headline,
      body_text: null,
      bullet_points: [],
      source_attribution: previewData.source,
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      theme: themeId,
      highlightColor,
      imageUrl: currentAsset?.storage_url || undefined,
    },
    {
      slide_number: 2,
      total_slides: 5,
      slide_type: "what_happened",
      header: slideCustomHeaders[2] || (isAmharicScript ? "ዋና ዋና ነጥቦች" : "THE CORE FACTS"),
      body_text: slideCustomBodies[2] || shortFact,
      bullet_points: [],
      source_attribution: previewData.source,
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      theme: themeId,
      highlightColor,
      imageUrl: currentAsset?.storage_url || undefined,
    },
    {
      slide_number: 3,
      total_slides: 5,
      slide_type: "key_facts",
      header: slideCustomHeaders[3] || (isAmharicScript ? "የተረጋገጡ ዝርዝሮች" : "KEY DEVELOPMENTS"),
      body_text: null,
      bullet_points: shortBullets,
      source_attribution: previewData.source,
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      theme: themeId,
      highlightColor,
      imageUrl: currentAsset?.storage_url || undefined,
    },
    {
      slide_number: 4,
      total_slides: 5,
      slide_type: "why_it_matters",
      header: slideCustomHeaders[4] || (isAmharicScript ? "ለምን አሳሳቢ ሆነ?" : "STRATEGIC IMPACT"),
      body_text: slideCustomBodies[4] || shortWhy,
      bullet_points: [],
      source_attribution: previewData.source,
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      theme: themeId,
      highlightColor,
      imageUrl: currentAsset?.storage_url || undefined,
    },
    {
      slide_number: 5,
      total_slides: 5,
      slide_type: "sources",
      header: slideCustomHeaders[5] || (isAmharicScript ? "የተረጋገጠ መረጃ" : "VERIFIED DESK"),
      body_text: slideCustomBodies[5] || (isAmharicScript ? "መረጃው በETHIOPIAN TIMES የዜና ማረጋገጫ ክፍል በተለያዩ ገለልተኛ ምንጮች ተረጋግጧል።" : "Corroborated across authorized monitoring desks and field dispatches."),
      bullet_points: [],
      source_attribution: previewData.source || "ETHIOPIAN TIMES Intelligence",
      accent: THEMES[themeId].accent as "green" | "red" | "gold",
      theme: themeId,
      highlightColor,
      imageUrl: currentAsset?.storage_url || undefined,
    },
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
      {showInspector && (
        <InspectorModal
          width={postMode === "single" ? FORMATS[format].width : 1080}
          height={postMode === "single" ? FORMATS[format].height : 1350}
          zoom={inspectorZoom}
          onZoomChange={setInspectorZoom}
          onClose={() => setShowInspector(false)}
          headerExtras={
            postMode === "carousel" ? (
              <div className="flex items-center gap-1.5 bg-ink-950 border border-ink-700 rounded-lg p-1 text-xs">
                <button
                  type="button"
                  disabled={carouselSlideIndex === 0}
                  onClick={() => setCarouselSlideIndex((prev) => Math.max(0, prev - 1))}
                  className="p-1 rounded hover:bg-ink-800 text-paper-300 hover:text-paper-100 disabled:opacity-30"
                  title="Previous slide"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <div className="flex items-center gap-1 px-1 font-mono">
                  {carouselSlides.map((_, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setCarouselSlideIndex(idx)}
                      className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${
                        carouselSlideIndex === idx
                          ? "bg-accent-green text-ink-950"
                          : "text-paper-400 hover:text-paper-100 hover:bg-ink-800"
                      }`}
                    >
                      P{idx + 1}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  disabled={carouselSlideIndex === carouselSlides.length - 1}
                  onClick={() => setCarouselSlideIndex((prev) => Math.min(carouselSlides.length - 1, prev + 1))}
                  className="p-1 rounded hover:bg-ink-800 text-paper-300 hover:text-paper-100 disabled:opacity-30"
                  title="Next slide"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : null
          }
        >
          {postMode === "single" ? (
            <>
              {format === "portrait" && <PortraitPost data={previewData} />}
              {format === "square" && <SquarePost data={previewData} />}
              {format === "story" && <StoryPost data={previewData} />}
            </>
          ) : (
            <CarouselCard
              slide={carouselSlides[carouselSlideIndex]}
              theme={themeId}
              highlightColor={highlightColor}
              category={previewData.category}
              dateLabel={previewData.dateLabel}
            />
          )}
        </InspectorModal>
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
                  <div className="flex items-center gap-2">
                    {/* Language Switcher Toggle */}
                    <div className="flex items-center gap-1 bg-ink-950 border border-ink-700 rounded-lg p-0.5 text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedLanguage("en");
                          if (activeEvent) {
                            setCustomHeadline(activeEvent.title);
                            setCustomDek(activeEvent.summary || "");
                            setCustomCategory(activeEvent.primary_category || "News");
                          } else {
                            setCustomHeadline(SAMPLE.headline);
                            setCustomDek(SAMPLE.dek || "");
                            setCustomCategory(SAMPLE.category);
                          }
                        }}
                        className={`px-2.5 py-1 rounded font-semibold transition-all ${
                          selectedLanguage === "en"
                            ? "bg-accent-green text-ink-950 shadow-sm"
                            : "text-paper-400 hover:text-paper-100"
                        }`}
                        title="English Broadcast Mode"
                      >
                        English (EN)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedLanguage("am");
                          const defaultAm = AMHARIC_PRESETS[0];
                          setCustomHeadline(defaultAm.headline);
                          setCustomDek(defaultAm.dek);
                          setCustomCategory(defaultAm.category);
                          setHighlightColor(defaultAm.highlightColor);
                          setSelectedCountry(defaultAm.country);
                        }}
                        className={`px-2.5 py-1 rounded font-semibold transition-all flex items-center gap-1 ${
                          selectedLanguage === "am"
                            ? "bg-accent-green text-ink-950 shadow-sm"
                            : "text-paper-400 hover:text-paper-100"
                        }`}
                        title="Amharic Broadcast News Mode"
                      >
                        <Languages className="h-3 w-3" />
                        አማርኛ (AM)
                      </button>
                    </div>

                    {activeEvent && (
                      <Badge variant={activeEvent.verification_score >= 75 ? "green" : "gold"}>
                        Score: {activeEvent.verification_score}
                      </Badge>
                    )}
                  </div>
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

                {/* Amharic Broadcast Presets Grid */}
                {selectedLanguage === "am" && (
                  <div className="space-y-1.5 p-3 rounded-card bg-ink-900/80 border border-ink-700/80 animate-in fade-in duration-150">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono uppercase tracking-wider text-accent-green font-bold flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" />
                        Amharic Broadcast Presets (Punchy 4-7 Words)
                      </span>
                      <span className="text-[10px] text-paper-400">Habesha News Style</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      {AMHARIC_PRESETS.map((preset) => (
                        <button
                          key={preset.key}
                          type="button"
                          onClick={() => {
                            setCustomHeadline(preset.headline);
                            setCustomDek(preset.dek);
                            setCustomCategory(preset.category);
                            setHighlightColor(preset.highlightColor);
                            setHighlightMode(preset.highlightMode || "auto");
                            setManualHighlightIndices([]);
                            setSelectedCountry(preset.country);
                          }}
                          className={`p-2.5 rounded-lg bg-ink-850 hover:bg-ink-800 text-left border transition-all text-xs ${
                            customHeadline === preset.headline
                              ? "border-accent-green bg-accent-green/10 text-paper-50"
                              : "border-ink-700 hover:border-accent-green/50 text-paper-200"
                          }`}
                        >
                          <div className="font-semibold text-paper-100 text-[11px] truncate flex items-center justify-between">
                            <span>{preset.label}</span>
                            {customHeadline === preset.headline && <Check className="h-3 w-3 text-accent-green" />}
                          </div>
                          <div className="text-[10px] text-paper-400 truncate mt-0.5">{preset.headline}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Editorial text authoring & live card tuning */}
                <div className="space-y-3 pt-2 border-t border-ink-700">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-xs uppercase tracking-label text-paper-500 font-mono">
                        Headline (Live on Card {isAmharicScript ? "· Noto Sans Ethiopic 900" : "· Anton Poster"})
                      </label>
                      <span className="text-[10px] font-mono text-paper-400">
                        {customHeadline.trim().split(/\s+/).filter(Boolean).length} words
                      </span>
                    </div>
                    <input
                      type="text"
                      value={customHeadline}
                      onChange={(e) => setCustomHeadline(e.target.value)}
                      placeholder={isAmharicScript ? "አጭር እና ግልጽ ዜና ርዕስ..." : "Short, punchy broadcast headline..."}
                      style={{
                        fontFamily: isAmharicScript ? "var(--font-ethiopic, 'Noto Sans Ethiopic', sans-serif)" : undefined,
                        fontWeight: isAmharicScript ? 700 : undefined,
                      }}
                      className="w-full h-9 rounded-card border border-ink-700 bg-ink-800 px-3 text-sm text-paper-100 focus:border-accent-green focus:outline-none"
                    />

                    {/* Interactive Click-to-Highlight Word Chips */}
                    {parsedHeadlineInfo.segments.length > 0 && (
                      <div className="space-y-1.5 pt-2.5">
                        <div className="flex items-center justify-between">
                          <label className="block text-[11px] uppercase tracking-label text-paper-400 font-mono flex items-center gap-1.5">
                            <Sparkles className="h-3 w-3 text-accent-green" />
                            Interactive Word Highlighter (Click to Toggle)
                          </label>
                          <div className="flex items-center gap-2">
                            {manualHighlightIndices.length > 0 && (
                              <button
                                type="button"
                                onClick={() => setManualHighlightIndices([])}
                                className="text-[10px] text-paper-400 hover:text-paper-200 underline font-mono"
                              >
                                Reset to {highlightMode.toUpperCase()}
                              </button>
                            )}
                            <span className="text-[10px] font-mono text-paper-500">
                              Mode: <strong className="text-accent-green">{parsedHeadlineInfo.detectedMode}</strong>
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1.5 p-2 rounded-card bg-ink-900 border border-ink-700/80">
                          {parsedHeadlineInfo.segments.map((seg) => {
                            const isHighlighted = seg.isHighlight;
                            return (
                              <button
                                key={seg.wordIndex}
                                type="button"
                                onClick={() => {
                                  let currentIndices = manualHighlightIndices.length > 0
                                    ? [...manualHighlightIndices]
                                    : [...parsedHeadlineInfo.highlightIndices];

                                  if (currentIndices.includes(seg.wordIndex)) {
                                    currentIndices = currentIndices.filter((idx) => idx !== seg.wordIndex);
                                  } else {
                                    currentIndices.push(seg.wordIndex);
                                  }
                                  setManualHighlightIndices(currentIndices.sort((a, b) => a - b));
                                }}
                                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all border ${
                                  isHighlighted
                                    ? "shadow-sm"
                                    : "border-ink-700 bg-ink-800 text-paper-400 hover:bg-ink-750 hover:text-paper-200"
                                }`}
                                style={{
                                  borderColor: isHighlighted ? highlightColor : undefined,
                                  backgroundColor: isHighlighted ? `${highlightColor}22` : undefined,
                                  color: isHighlighted ? (highlightColor === "#FFFFFF" ? "#FFFFFF" : highlightColor) : undefined,
                                }}
                              >
                                {seg.text}
                              </button>
                            );
                          })}
                        </div>
                        <div className="text-[10px] text-paper-500 flex items-center justify-between">
                          <span>💡 Wrap words in <code className="text-paper-300 font-mono font-bold">{"{braces}"}</code> in text to highlight anywhere.</span>
                          {parsedHeadlineInfo.highlightedWords.length > 0 && (
                            <span className="text-paper-400 font-mono">
                              Highlighted: <span style={{ color: highlightColor }} className="font-bold">{parsedHeadlineInfo.highlightedWords.join(" ")}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">
                      Dek / Subheading {isAmharicScript ? "(1 አጭር ዓረፍተ ነገር)" : "(1 Short Sentence)"}
                    </label>
                    <textarea
                      rows={2}
                      value={customDek}
                      onChange={(e) => setCustomDek(e.target.value)}
                      placeholder={isAmharicScript ? "ዝርዝር መግለጫ..." : "Subheading context..."}
                      style={{
                        fontFamily: isAmharicScript ? "var(--font-ethiopic, 'Noto Sans Ethiopic', sans-serif)" : undefined,
                      }}
                      className="w-full rounded-card border border-ink-700 bg-ink-800 p-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none resize-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Category Pill</label>
                      <input
                        type="text"
                        value={customCategory}
                        onChange={(e) => setCustomCategory(e.target.value)}
                        placeholder={isAmharicScript ? "ለምሳሌ: ስፖርት, ኢኮኖሚ" : "e.g. Sports, Economy"}
                        className="w-full h-8 rounded-card border border-ink-700 bg-ink-800 px-2.5 text-xs text-paper-200 focus:border-accent-green focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs uppercase tracking-label text-paper-500 mb-1 font-mono">Primary Region / Country</label>
                      <div className="h-8 rounded-card border border-ink-800 bg-ink-900 px-2.5 flex items-center text-xs text-paper-400">
                        {activeEvent?.primary_region || selectedCountry || "National / Pan-Ethiopia"}
                      </div>
                    </div>
                  </div>
                </div>
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
                        <div className="text-[9px] text-paper-500">Multi-tier entity cascade</div>
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
                {(themeId === "broadcast_impact" || themeId === "headline_impact" || themeId === "country_spotlight") && (
                  <div className="space-y-3 p-3 rounded-card bg-ink-900/90 border border-ink-700/80">
                    {/* A. Non-generic curated editorial highlight palette */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-xs uppercase tracking-label text-paper-400 font-mono flex items-center gap-1.5 font-bold">
                          <Palette className="h-3.5 w-3.5 text-accent-green" />
                          Curated Broadcast Highlight Palette
                        </label>
                        <span className="text-[10px] font-mono text-paper-500">
                          9 Editorial Tones
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        {HIGHLIGHT_PALETTES.map((swatch) => {
                          const isSelected = highlightColor.toLowerCase() === swatch.hex.toLowerCase();
                          return (
                            <button
                              key={swatch.id}
                              type="button"
                              onClick={() => {
                                setHighlightColor(swatch.hex);
                                setCustomHexInput("");
                              }}
                              className={`flex flex-col items-start p-2 rounded-lg text-left transition-all border ${
                                isSelected
                                  ? "bg-ink-800 border-accent-green shadow-sm ring-1 ring-accent-green/40"
                                  : "bg-ink-850 border-ink-700/80 hover:border-ink-600 hover:bg-ink-800"
                              }`}
                              title={`${swatch.name} — ${swatch.mood}`}
                            >
                              <div className="flex items-center justify-between w-full mb-1">
                                <span
                                  className="w-3.5 h-3.5 rounded-full border border-black/40 shadow-inner shrink-0"
                                  style={{ backgroundColor: swatch.hex }}
                                />
                                <span className="text-[9px] font-mono text-paper-400 truncate ml-1">
                                  {swatch.category}
                                </span>
                              </div>
                              <span className="text-xs font-semibold text-paper-100 truncate w-full">
                                {swatch.name}
                              </span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Custom Hex Color Picker Bar */}
                      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-ink-800/80">
                        <label className="text-[10px] uppercase font-mono text-paper-400 shrink-0">Custom Hex:</label>
                        <div className="flex items-center gap-1.5 bg-ink-950 border border-ink-700 rounded-md px-2 py-0.5 w-full">
                          <input
                            type="color"
                            value={highlightColor.startsWith("#") && highlightColor.length === 7 ? highlightColor : "#00F0FF"}
                            onChange={(e) => {
                              setHighlightColor(e.target.value);
                              setCustomHexInput(e.target.value);
                            }}
                            className="w-5 h-5 rounded cursor-pointer bg-transparent border-0 p-0"
                            title="Color picker"
                          />
                          <input
                            type="text"
                            value={customHexInput || highlightColor}
                            onChange={(e) => {
                              const val = e.target.value;
                              setCustomHexInput(val);
                              if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                                setHighlightColor(val);
                              }
                            }}
                            placeholder="#00F0FF"
                            className="text-xs font-mono bg-transparent text-paper-100 focus:outline-none w-full uppercase"
                          />
                        </div>
                      </div>
                    </div>

                    {/* B. Highlight Position & Strategy Selector */}
                    <div className="pt-2 border-t border-ink-800">
                      <div className="flex items-center justify-between mb-1.5">
                        <label className="block text-xs uppercase tracking-label text-paper-400 font-mono font-bold">
                          Highlight Placement Strategy
                        </label>
                        <span className="text-[10px] font-mono text-accent-green">
                          {highlightMode === "auto" && "Keyword / Verb AI"}
                          {highlightMode === "middle" && "Center Pivot"}
                          {highlightMode === "end" && "Classic Punchline"}
                          {highlightMode === "start" && "Lead Subject"}
                          {highlightMode === "none" && "Monochrome White"}
                        </span>
                      </div>
                      <div className="grid grid-cols-5 gap-1">
                        {[
                          { id: "auto" as HighlightMode, label: "🤖 Smart", desc: "Keyword / action-verb detection" },
                          { id: "middle" as HighlightMode, label: "🎯 Middle", desc: "Highlights central pivot words" },
                          { id: "end" as HighlightMode, label: "🔻 End", desc: "Bottom punchline highlight" },
                          { id: "start" as HighlightMode, label: "👤 Start", desc: "Lead subject / actor focus" },
                          { id: "none" as HighlightMode, label: "⚪ Plain", desc: "All white typography" },
                        ].map((m) => (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => {
                              setHighlightMode(m.id);
                              setManualHighlightIndices([]);
                            }}
                            className={`py-1.5 px-1 rounded text-center text-xs font-semibold transition-all border ${
                              highlightMode === m.id
                                ? "bg-ink-750 text-paper-50 border-accent-green font-bold shadow-sm"
                                : "bg-ink-850 text-paper-400 border-ink-700 hover:bg-ink-800 hover:text-paper-200"
                            }`}
                            title={m.desc}
                          >
                            {m.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                {themeId === "country_spotlight" && (
                  <div className="space-y-2 pt-1 border-t border-ink-800">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs uppercase tracking-label text-paper-400 font-mono flex items-center gap-1.5">
                        <Globe className="h-3.5 w-3.5 text-accent-green" /> National Flag Spotlight
                      </label>
                      <span className="text-[11px] font-mono text-paper-400">
                        Target: <strong className="text-accent-green">{selectedCountry}</strong>
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {POPULAR_COUNTRIES.map((c) => (
                        <button
                          key={c.code}
                          type="button"
                          onClick={() => setSelectedCountry(c.label)}
                          className={`px-2.5 py-1 rounded-card text-xs font-mono flex items-center gap-1.5 border transition-all ${
                            selectedCountry.toLowerCase() === c.label.toLowerCase() ||
                            selectedCountry.toLowerCase().includes(c.label.toLowerCase())
                              ? "border-accent-green bg-accent-green/15 text-paper-50 font-bold"
                              : "border-ink-700 bg-ink-800 text-paper-400 hover:bg-ink-700 hover:text-paper-200"
                          }`}
                        >
                          <span>{c.flag}</span>
                          <span>{c.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
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
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs uppercase tracking-label text-paper-500 font-mono">Carousel Slide Navigator</label>
                      <span className="text-[11px] font-mono text-accent-green font-bold">Slide {carouselSlideIndex + 1} of 5</span>
                    </div>
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

                    {/* Inline Slide Text Customizer for active slide */}
                    <div className="rounded-card border border-ink-700 bg-ink-800/80 p-3 space-y-2.5">
                      <div className="flex items-center justify-between text-xs font-mono text-paper-300">
                        <span className="font-bold text-paper-100">Slide {carouselSlideIndex + 1}: {carouselSlides[carouselSlideIndex].slide_type.replace("_", " ").toUpperCase()}</span>
                        {(slideCustomHeaders[carouselSlideIndex + 1] || slideCustomBodies[carouselSlideIndex + 1]) && (
                          <button
                            type="button"
                            onClick={() => {
                              setSlideCustomHeaders((prev) => { const next = { ...prev }; delete next[carouselSlideIndex + 1]; return next; });
                              setSlideCustomBodies((prev) => { const next = { ...prev }; delete next[carouselSlideIndex + 1]; return next; });
                            }}
                            className="text-[10px] text-accent-gold hover:underline"
                          >
                            Reset to Auto
                          </button>
                        )}
                      </div>
                      <div>
                        <label className="block text-[11px] text-paper-400 font-mono mb-1">Headline / Header</label>
                        <input
                          type="text"
                          value={slideCustomHeaders[carouselSlideIndex + 1] ?? carouselSlides[carouselSlideIndex].header}
                          onChange={(e) => setSlideCustomHeaders((prev) => ({ ...prev, [carouselSlideIndex + 1]: e.target.value }))}
                          className="w-full h-8 rounded-card border border-ink-600 bg-ink-900 px-2.5 text-xs text-paper-50 focus:border-accent-green focus:outline-none font-sans"
                        />
                      </div>
                      {carouselSlides[carouselSlideIndex].slide_type !== "cover" && (
                        <div>
                          <label className="block text-[11px] text-paper-400 font-mono mb-1">Short Body Statement (1-2 sentences)</label>
                          <textarea
                            rows={2}
                            value={slideCustomBodies[carouselSlideIndex + 1] ?? carouselSlides[carouselSlideIndex].body_text ?? ""}
                            onChange={(e) => setSlideCustomBodies((prev) => ({ ...prev, [carouselSlideIndex + 1]: e.target.value }))}
                            className="w-full rounded-card border border-ink-600 bg-ink-900 p-2 text-xs text-paper-50 focus:border-accent-green focus:outline-none font-sans resize-none"
                          />
                        </div>
                      )}
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
                  <span>Live Canvas ({postMode === "single" ? `${FORMATS[format].width}×${FORMATS[format].height}` : "1080×1350"})</span>
                </div>
                <div className="flex items-center gap-2">
                  {postMode === "carousel" && (
                    <div className="flex items-center bg-ink-900 border border-ink-700 rounded p-0.5 text-[10px] font-mono">
                      <button
                        type="button"
                        onClick={() => setCarouselViewMode("deck")}
                        className={`px-2 py-0.5 rounded transition-colors ${carouselViewMode === "deck" ? "bg-accent-green text-ink-950 font-bold" : "text-paper-400 hover:text-paper-200"}`}
                      >
                        All 5 Pages
                      </button>
                      <button
                        type="button"
                        onClick={() => setCarouselViewMode("single")}
                        className={`px-2 py-0.5 rounded transition-colors ${carouselViewMode === "single" ? "bg-accent-green text-ink-950 font-bold" : "text-paper-400 hover:text-paper-200"}`}
                      >
                        Focus Slide
                      </button>
                    </div>
                  )}
                  <div className="flex items-center bg-ink-900 border border-ink-700 rounded p-0.5 text-[10px] font-mono">
                    {[380, 460, 520].map((sz) => (
                      <button
                        key={sz}
                        type="button"
                        onClick={() => setPreviewTarget(sz)}
                        className={`px-1.5 py-0.5 rounded transition-colors ${previewTarget === sz ? "bg-accent-green text-ink-950 font-bold" : "text-paper-400 hover:text-paper-200"}`}
                      >
                        {sz}px
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    onClick={() => setShowInspector(true)}
                    className="h-6 px-2 text-[10px] flex items-center gap-1 border-accent-green/40 hover:border-accent-green text-accent-green bg-accent-green/5 hover:bg-accent-green/10 font-mono"
                    title="Inspect raw 1080x1350 4K canvas at 100% full scale"
                  >
                    <Maximize2 className="h-3 w-3" />
                    <span>4K Inspector</span>
                  </Button>
                  <Badge variant="muted" className="font-mono text-[10px]">
                    {postMode === "single" ? `${format.toUpperCase()} · ${THEMES[themeId].label}` : `SLIDE ${carouselSlideIndex + 1} OF 5`}
                  </Badge>
                </div>
              </div>
              <div className="flex justify-center bg-ink-950 border border-ink-700 rounded-card p-6 overflow-hidden shadow-inner min-h-[620px] items-center">
                {postMode === "single" ? (
                  <ScaledPreview width={FORMATS[format].width} height={FORMATS[format].height} target={previewTarget}>
                    {format === "portrait" && <PortraitPost data={previewData} />}
                    {format === "square" && <SquarePost data={previewData} />}
                    {format === "story" && <StoryPost data={previewData} />}
                  </ScaledPreview>
                ) : carouselViewMode === "deck" ? (
                  <div className="w-full flex flex-col gap-4 py-2">
                    <div className="flex items-center justify-between pb-2 border-b border-ink-800 text-xs font-mono">
                      <div className="flex items-center gap-2 text-paper-200">
                        <span className="text-accent-green font-bold flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5" /> 5-PAGE BROADCAST CAROUSEL
                        </span>
                        <span className="text-paper-500">· Full Story Flow</span>
                      </div>
                      <span className="text-paper-400 text-[11px]">Click any card to edit / select</span>
                    </div>
                    <div className="w-full overflow-x-auto pb-4 pt-1">
                      <div className="flex gap-5 items-start min-w-max px-2">
                        {carouselSlides.map((s, idx) => (
                          <div
                            key={s.slide_number}
                            onClick={() => setCarouselSlideIndex(idx)}
                            className={`flex flex-col items-center gap-2 cursor-pointer transition-all ${
                              carouselSlideIndex === idx
                                ? "ring-2 ring-accent-green ring-offset-2 ring-offset-ink-950 rounded-card scale-[1.02]"
                                : "opacity-80 hover:opacity-100 hover:scale-[1.01]"
                            }`}
                          >
                            <div className="flex items-center justify-between w-full px-1 text-[11px] font-mono">
                              <span className={carouselSlideIndex === idx ? "font-bold text-accent-green" : "text-paper-400"}>
                                PAGE {idx + 1} OF 5
                              </span>
                              <span className="text-paper-500 text-[10px] uppercase">
                                {s.slide_type === "cover" ? "COVER" : s.slide_type === "what_happened" ? "FACTS" : s.slide_type === "key_facts" ? "POINTS" : s.slide_type === "why_it_matters" ? "IMPACT" : "SOURCES"}
                              </span>
                            </div>
                            <ScaledPreview width={1080} height={1350} target={260}>
                              <CarouselCard
                                slide={s}
                                theme={themeId}
                                highlightColor={highlightColor}
                                category={previewData.category}
                                dateLabel={previewData.dateLabel}
                              />
                            </ScaledPreview>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setCarouselSlideIndex(idx);
                                setCarouselViewMode("single");
                              }}
                              className="text-[11px] font-mono text-accent-green hover:underline flex items-center gap-1 pt-1"
                            >
                              <span>Focus Slide {idx + 1} ↗</span>
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-4">
                    <ScaledPreview width={1080} height={1350} target={previewTarget}>
                      <CarouselCard
                        slide={carouselSlides[carouselSlideIndex]}
                        theme={themeId}
                        highlightColor={highlightColor}
                        category={previewData.category}
                        dateLabel={previewData.dateLabel}
                      />
                    </ScaledPreview>
                    <div className="flex items-center gap-3 pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={carouselSlideIndex === 0}
                        onClick={() => setCarouselSlideIndex((prev) => Math.max(0, prev - 1))}
                        className="h-8 text-xs font-mono bg-ink-900 border-ink-700 hover:bg-ink-800"
                      >
                        <ChevronLeft className="h-3.5 w-3.5 mr-1" /> Previous Slide
                      </Button>
                      <span className="text-xs font-mono text-paper-200 font-bold px-2">
                        Slide {carouselSlideIndex + 1} of 5
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={carouselSlideIndex === 4}
                        onClick={() => setCarouselSlideIndex((prev) => Math.min(4, prev + 1))}
                        className="h-8 text-xs font-mono bg-ink-900 border-ink-700 hover:bg-ink-800"
                      >
                        Next Slide <ChevronRight className="h-3.5 w-3.5 ml-1" />
                      </Button>
                    </div>
                  </div>
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
