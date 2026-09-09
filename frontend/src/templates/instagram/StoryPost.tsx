import { PostTemplate, type PostTemplateData } from "./PostTemplate";

export function StoryPost({ data }: { data: PostTemplateData }) {
  return <PostTemplate format="story" data={data} />;
}
