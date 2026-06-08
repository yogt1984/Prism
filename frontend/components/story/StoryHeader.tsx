import Breadcrumb from "./Breadcrumb";
import CategoryPill from "@/components/dashboard/CategoryPill";
import TimeAgo from "@/components/dashboard/TimeAgo";
import QualityIndicator from "./QualityIndicator";
import type { StoryDetail } from "@/lib/types";

export default function StoryHeader({ story }: { story: StoryDetail }) {
  const categories = story.categories.split(",").filter(Boolean);

  return (
    <header className="space-y-3">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Stories", href: "/stories" },
          { label: story.headline },
        ]}
      />
      <h1 className="text-2xl font-bold lg:text-3xl">{story.headline}</h1>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {categories.map((cat) => (
          <CategoryPill key={cat} category={cat.trim()} />
        ))}
        <TimeAgo date={story.first_seen} />
        <span className="text-gray-400">|</span>
        <span className="text-gray-500">
          {story.article_count} sources
        </span>
        <QualityIndicator score={story.quality_score} />
      </div>
    </header>
  );
}
