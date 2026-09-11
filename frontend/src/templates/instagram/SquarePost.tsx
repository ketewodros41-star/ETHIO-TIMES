import { PostTemplate, type PostTemplateData } from "./PostTemplate";

export function SquarePost({ data }: { data: PostTemplateData }) {
  return <PostTemplate format="square" data={data} />;
}
