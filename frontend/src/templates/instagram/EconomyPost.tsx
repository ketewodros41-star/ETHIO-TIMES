// TODO: deep-spec pending (Phase 6) — stub renders as PostTemplate with green accent
import { PostTemplate, type PostTemplateData } from "./PostTemplate";
import type { InstagramFormat } from "./formats";
export function EconomyPost({ format, data }: { format: InstagramFormat; data: PostTemplateData }) {
  return <PostTemplate format={format} data={{ ...data, accent: "green" }} />;
}
