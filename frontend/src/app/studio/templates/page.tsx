"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, postsApi } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { VISUAL_STYLES } from "@/lib/design-tokens";
import {
  FORMATS,
  PortraitPost,
  SquarePost,
  StoryPost,
  THEMES,
  THEME_IDS,
  type InstagramFormat,
  type ThemeId,
  type PostTemplateData,
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

/**
 * Scales a true-pixel post (1080px wide) down to fit the preview column while
 * keeping the underlying element at 1:1 for later screenshotting.
 */
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
    <div style={{ width: target, height: height * scale }} className="overflow-hidden rounded-card border border-ink-700 bg-ink-900">
      <div style={{ transform: `scale(${scale})`, transformOrigin: "top left", width, height }}>
        {children}
      </div>
    </div>
  );
}

export default function TemplatesStudioPage() {
  const [selectedEventId, setSelectedEventId] = useState<string>("");
  const [format, setFormat] = useState<InstagramFormat>("portrait");
  const [themeId, setThemeId] = useState<ThemeId>("verified_brief");

  // Fetch confirmed events
  const { data: eventsData } = useQuery({
    queryKey: ["studio_events"],
    queryFn: () =>
      api.listEvents({
        limit: 30,
        verification_status: "confirmed",
      }),
  });

  const composeMutation = useMutation({
    mutationFn: () => postsApi.compose({ event_id: selectedEventId, format, theme: themeId }),
    onSuccess: () => alert("Post queued — view in Posts queue"),
  });

  const events = eventsData?.items ?? [];
  const selectedEvent = events.find((e) => e.id === selectedEventId);

  const previewData: PostTemplateData = selectedEvent
    ? {
        category: selectedEvent.primary_category || "News",
        headline: selectedEvent.title,
        dek: selectedEvent.summary || undefined,
        source: "ETHIOTIMES",
        dateLabel: new Date(selectedEvent.created_at).toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }).toUpperCase(),
        theme: themeId,
        accent: THEMES[themeId].accent,
      }
    : { ...SAMPLE, theme: themeId, accent: THEMES[themeId].accent };

  return (
    <PageShell title="Post Studio">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Studio Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-xs uppercase tracking-label text-paper-500 mb-2">Source Event</label>
              <select
                value={selectedEventId}
                onChange={(e) => setSelectedEventId(e.target.value)}
                className="w-full h-10 rounded-card border border-ink-600 bg-ink-800 px-3 text-sm text-paper-50"
              >
                <option value="">-- Use sample data --</option>
                {events.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title} (Score: {e.verification_score})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs uppercase tracking-label text-paper-500 mb-2">Theme</label>
              <div className="flex flex-wrap gap-2">
                {THEME_IDS.map((tid) => (
                  <button
                    key={tid}
                    onClick={() => setThemeId(tid)}
                    className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                      themeId === tid ? "bg-ink-700 text-paper-50 border border-ink-500" : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                    }`}
                  >
                    {THEMES[tid].label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs uppercase tracking-label text-paper-500 mb-2">Format</label>
              <div className="flex gap-2">
                {(Object.keys(FORMATS) as InstagramFormat[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFormat(f)}
                    className={`px-3 py-1.5 rounded-card text-xs transition-colors ${
                      format === f ? "bg-ink-700 text-paper-50 border border-ink-500" : "bg-ink-800 text-paper-300 border border-ink-700 hover:bg-ink-700"
                    }`}
                  >
                    {FORMATS[f].label}
                  </button>
                ))}
              </div>
            </div>

            <Button
              disabled={!selectedEventId || composeMutation.isPending}
              onClick={() => composeMutation.mutate()}
              className="mt-4"
            >
              Compose Post
            </Button>
          </CardContent>
        </Card>

        <div className="flex justify-center bg-ink-900 border border-ink-700 rounded-card p-8 overflow-hidden">
          <ScaledPreview width={FORMATS[format].width} height={FORMATS[format].height} target={400}>
            {format === "portrait" && <PortraitPost data={previewData} />}
            {format === "square" && <SquarePost data={previewData} />}
            {format === "story" && <StoryPost data={previewData} />}
          </ScaledPreview>
        </div>
      </div>
    </PageShell>
  );
}
