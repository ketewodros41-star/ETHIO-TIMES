import { PageShell } from "@/components/page-shell";
import { ArticlesContent } from "./articles-content";

export default function ArticlesPage() {
  return (
    <PageShell title="Articles">
      <ArticlesContent />
    </PageShell>
  );
}
