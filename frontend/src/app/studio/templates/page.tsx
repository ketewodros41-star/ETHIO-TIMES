import { PageShell } from "@/components/page-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { VISUAL_STYLES } from "@/lib/design-tokens";
import {
  FORMATS,
  PortraitPost,
  SquarePost,
  StoryPost,
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
};

const SAMPLE_GOLD: PostTemplateData = {
  ...SAMPLE,
  category: "Analysis",
  headline: "Inside the corridor economy reshaping the Horn of Africa",
  dek: "A closer look at the trade routes redrawing regional power.",
  source: "Ethiopia Insight",
  accent: "gold",
  style: "Cinematic Editorial",
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
    <div style={{ width: target, height: height * scale }} className="overflow-hidden rounded-card border border-ink-700">
      <div style={{ transform: `scale(${scale})`, transformOrigin: "top left", width, height }}>
        {children}
      </div>
    </div>
  );
}

export default function TemplatesStudioPage() {
  return (
    <PageShell title="Post Studio">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Instagram templates</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-paper-300">
            <p>
              Composition stubs rendered at true pixel size. A later phase will
              screenshot these routes with Playwright to produce final PNGs, and
              the Visual Director will select a visual style and generate the
              image zone.
            </p>
            <div className="flex flex-wrap gap-2 pt-2">
              {Object.values(FORMATS).map((f) => (
                <Badge key={f.label} variant="default">
                  {f.label}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-label text-paper-500">
              Portrait · 1080×1350
            </p>
            <ScaledPreview width={1080} height={1350} target={320}>
              <PortraitPost data={SAMPLE} />
            </ScaledPreview>
          </div>
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-label text-paper-500">
              Square · 1080×1080
            </p>
            <ScaledPreview width={1080} height={1080} target={320}>
              <SquarePost data={SAMPLE_GOLD} />
            </ScaledPreview>
          </div>
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-label text-paper-500">
              Story · 1080×1920
            </p>
            <ScaledPreview width={1080} height={1920} target={260}>
              <StoryPost data={SAMPLE} />
            </ScaledPreview>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Documented visual styles (for the Visual Director)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {VISUAL_STYLES.map((s) => (
              <Badge key={s} variant="muted">
                {s}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
