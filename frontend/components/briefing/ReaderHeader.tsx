import Link from "next/link";
import StoryCountBadge from "./StoryCountBadge";
import FormatBadge from "./FormatBadge";
import type { BriefingDetail, BriefingFormat } from "@/lib/types";

export default function ReaderHeader({
  briefing,
  format,
}: {
  briefing: BriefingDetail;
  format?: BriefingFormat;
}) {
  const date = new Date(briefing.created_at);
  const dateStr = date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const timeStr = date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });

  return (
    <header className="space-y-2" data-testid="reader-header">
      <Link
        href="/briefings"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-violet-600"
        data-testid="back-link"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        All Briefings
      </Link>
      <h1 className="text-2xl font-bold">{dateStr}</h1>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-gray-500">{timeStr}</span>
        <StoryCountBadge count={briefing.story_count} />
        {format && <FormatBadge format={format} />}
      </div>
    </header>
  );
}
