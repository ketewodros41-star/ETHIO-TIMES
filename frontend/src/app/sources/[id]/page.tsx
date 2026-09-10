import { PageShell } from "@/components/page-shell";
import { SourceDetailContent } from "./source-detail-content";

export default function SourceDetailPage({ params }: { params: { id: string } }) {
  return (
    <PageShell title="News Source">
      <SourceDetailContent id={params.id} />
    </PageShell>
  );
}
