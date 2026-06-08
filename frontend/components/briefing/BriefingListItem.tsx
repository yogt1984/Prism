import Link from "next/link";
import StoryCountBadge from "./StoryCountBadge";
import SentBadge from "./SentBadge";
import PromptVersionTag from "./PromptVersionTag";
import type { Briefing } from "@/lib/types";

function formatDate(iso: string) {
  const d = new Date(iso);
  const day = d.toLocaleDateString("en-US", { weekday: "short" });
  const date = d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const time = d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
  return { day, date, time };
}

export default function BriefingListItem({
  briefing,
}: {
  briefing: Briefing;
}) {
  const { day, date, time } = formatDate(briefing.created_at);

  return (
    <Link
      href={`/briefings/${briefing.id}`}
      className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 transition-colors"
      data-testid="briefing-list-item"
    >
      <div className="w-28 flex-shrink-0" data-testid="date-column">
        <p className="text-sm font-medium text-gray-800">{day}</p>
        <p className="text-xs text-gray-500">{date}</p>
        <p className="text-xs text-gray-400">{time}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
        <StoryCountBadge count={briefing.story_count} />
        <SentBadge sent={briefing.sent} />
        <PromptVersionTag version={briefing.prompt_version} />
      </div>
      <svg
        className="w-5 h-5 text-gray-400 flex-shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 5l7 7-7 7"
        />
      </svg>
    </Link>
  );
}

export { formatDate };
