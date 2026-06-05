import Link from "next/link";
import type { Briefing, BriefingDetail } from "@/lib/types";

interface TodayBriefingCardProps {
  briefing?: Briefing | null;
  detail?: BriefingDetail | null;
  isLoading: boolean;
  onTrigger?: () => void;
  isTriggerPending?: boolean;
}

export default function TodayBriefingCard({
  briefing,
  detail,
  isLoading,
  onTrigger,
  isTriggerPending,
}: TodayBriefingCardProps) {
  if (isLoading) {
    return (
      <div
        className="rounded-lg border border-gray-200 p-6"
        data-testid="briefing-skeleton"
      >
        <div className="h-4 w-40 animate-pulse rounded bg-gray-200 mb-4" />
        <div className="h-32 animate-pulse rounded bg-gray-100" />
      </div>
    );
  }

  if (!briefing) {
    return (
      <div
        className="rounded-lg border border-gray-200 p-6 text-center"
        data-testid="briefing-empty"
      >
        <p className="text-gray-500">
          No briefing yet &mdash; your first one arrives at 7am UTC
        </p>
        {onTrigger && (
          <button
            onClick={onTrigger}
            disabled={isTriggerPending}
            className="mt-3 rounded-md bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {isTriggerPending ? "Generating..." : "Generate now"}
          </button>
        )}
      </div>
    );
  }

  const preview = detail?.content_html
    ? detail.content_html.replace(/<[^>]+>/g, "").slice(0, 300)
    : null;

  return (
    <div className="rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Today&apos;s Briefing</h2>
        <span className="text-sm text-gray-500">
          {new Date(briefing.created_at).toLocaleDateString()}
        </span>
      </div>
      {preview && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-3">{preview}</p>
      )}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">
          {briefing.story_count} stories
        </span>
        <Link
          href={`/briefings/${briefing.id}`}
          className="text-sm font-medium text-violet-600 hover:underline"
        >
          View full briefing &rarr;
        </Link>
      </div>
    </div>
  );
}
