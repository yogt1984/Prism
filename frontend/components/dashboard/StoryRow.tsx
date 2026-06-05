import Link from "next/link";
import TimeAgo from "./TimeAgo";
import type { Story } from "@/lib/types";

const CATEGORY_DOT_COLORS: Record<string, string> = {
  finance: "bg-emerald-500",
  politics: "bg-red-500",
  technology: "bg-blue-500",
  sports: "bg-orange-500",
  culture: "bg-purple-500",
  science: "bg-cyan-500",
  health: "bg-pink-500",
  world: "bg-amber-500",
};

export default function StoryRow({ story }: { story: Story }) {
  const firstCategory = story.categories.split(",")[0]?.trim() || "";
  const dotColor = CATEGORY_DOT_COLORS[firstCategory] ?? "bg-gray-400";

  return (
    <Link
      href={`/stories/${story.id}`}
      className="flex items-center gap-3 py-3 px-2 hover:bg-gray-50 rounded transition-colors"
      data-testid="story-row"
    >
      <span
        className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`}
        data-testid="category-dot"
      />
      <span className="flex-1 text-sm font-medium truncate">
        {story.headline}
      </span>
      <span className="text-xs text-gray-500 flex-shrink-0">
        {story.resonance_score.toFixed(1)}
      </span>
      <span className="text-xs text-gray-400 flex-shrink-0">
        <TimeAgo date={story.first_seen} />
      </span>
    </Link>
  );
}

export { CATEGORY_DOT_COLORS };
