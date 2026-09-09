import { PostTemplate, type PostTemplateData } from "./PostTemplate";

export function PortraitPost({ data }: { data: PostTemplateData }) {
  return <PostTemplate format="portrait" data={data} />;
}
