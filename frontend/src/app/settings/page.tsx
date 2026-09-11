import { PageShell } from "@/components/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/api";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-ink-800 py-2 last:border-0">
      <span className="text-sm text-paper-500">{label}</span>
      <span className="font-mono text-sm text-paper-300">{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <PageShell title="Settings">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <Row label="API base URL" value={API_BASE} />
            <Row label="Dashboard" value="Next.js · App Router" />
            <Row label="Phase" value="1 — Foundation" />
            <Row label="Version" value="0.1.0" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Secrets &amp; credentials</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-paper-300">
              Secret values are never displayed or stored in the dashboard. They
              are provided via environment variables (see{" "}
              <span className="font-mono text-paper-500">.env.example</span>).
            </p>
            <div className="space-y-1">
              <Row label="DATABASE_URL" value={<Badge variant="muted">env</Badge>} />
              <Row label="REDIS_URL" value={<Badge variant="muted">env</Badge>} />
              <Row label="JWT_SECRET" value={<Badge variant="muted">env</Badge>} />
              <Row label="GEMINI_API_KEY" value={<Badge variant="muted">env</Badge>} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ingestion</CardTitle>
          </CardHeader>
          <CardContent>
            <Row label="RSS adapter" value={<Badge variant="green">enabled</Badge>} />
            <Row
              label="Website crawler"
              value={<Badge variant="muted">Phase 2</Badge>}
            />
            <Row label="Telegram" value={<Badge variant="muted">Phase 1.5</Badge>} />
            <Row
              label="Beat schedule"
              value="poll due sources · 5 min"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI providers</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-paper-300">
              Provider abstractions are wired; analysis and image pipelines are
              enabled in later phases.
            </p>
            <Row label="Text (Gemini)" value={<Badge variant="muted">stub</Badge>} />
            <Row label="Images (Imagen)" value={<Badge variant="muted">stub</Badge>} />
            <Row label="Embeddings" value={<Badge variant="muted">Phase 2</Badge>} />
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
