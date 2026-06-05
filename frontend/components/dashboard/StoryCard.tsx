import Link from "next/link";
import CategoryPill from "./CategoryPill";
import ResonanceBadge from "./ResonanceBadge";
import TimeAgo from "./TimeAgo";
import type { Story } from "@/lib/types";

export default function StoryCard({ story }: { story: Story }) {
  const categories = story.categories.split(",").filter(Boolean);

  return (
    <Link
      href={`/stories/${story.id}`}
      className="block min-w-[240px] rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
      data-testid="story-card"
    >
      <div className="flex flex-wrap gap-1 mb-2">
        {categories.map((cat) => (
          <CategoryPill key={cat} category={cat.trim()} />
        ))}
      </div>
      <h3 className="font-medium text-sm line-clamp-2 mb-2">
        {story.headline}
      </h3>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <ResonanceBadge score={story.resonance_score} />
        <span>{story.article_count} sources</span>
        <TimeAgo date={story.first_seen} />
      </div>
    </Link>
  );
}
