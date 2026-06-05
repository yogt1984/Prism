"use client";

import StoryRow from "./StoryRow";
import { useRecentStoriesInfinite } from "@/lib/hooks";

export default function RecentStoriesFeed() {
  const { data, isLoading, isFetchingNextPage, hasNextPage, fetchNextPage } =
    useRecentStoriesInfinite();

  const stories = data?.pages.flat() ?? [];

  if (isLoading) {
    return (
      <section>
        <h2 className="text-lg font-semibold mb-3">Recent Stories</h2>
        <div className="space-y-2" data-testid="recent-skeleton">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded bg-gray-100"
            />
          ))}
        </div>
      </section>
    );
  }

  if (stories.length === 0) {
    return (
      <section>
        <h2 className="text-lg font-semibold mb-3">Recent Stories</h2>
        <p className="text-sm text-gray-500" data-testid="recent-empty">
          No stories discovered yet. The pipeline runs every 2 hours.
        </p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="text-lg font-semibold mb-3">Recent Stories</h2>
      <div className="divide-y divide-gray-100">
        {stories.map((story) => (
          <StoryRow key={story.id} story={story} />
        ))}
      </div>
      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-3 w-full rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          data-testid="load-more"
        >
          {isFetchingNextPage ? "Loading..." : "Load more"}
        </button>
      )}
    </section>
  );
}
