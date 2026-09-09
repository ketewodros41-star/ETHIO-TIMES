import { PageShell } from "@/components/page-shell";
import { EventDetailContent } from "./event-detail-content";

export default function EventDetailPage({ params }: { params: { id: string } }) {
  return (
    <PageShell title="Event Detail">
      <EventDetailContent id={params.id} />
    </PageShell>
  );
}
