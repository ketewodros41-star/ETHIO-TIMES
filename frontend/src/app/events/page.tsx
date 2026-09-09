import { PageShell } from "@/components/page-shell";
import { EventsContent } from "./events-content";

export default function EventsPage() {
  return (
    <PageShell title="Event Feed">
      <EventsContent />
    </PageShell>
  );
}
