import Link from "next/link";
import StoryCard from "./StoryCard";
import type { Story } from "@/lib/types";

interface TopStoriesSectionProps {
  stories: Story[];
  isLoading: boolean;
}

export default function TopStoriesSection({
  stories,
  isLoading,
}: TopStoriesSectionProps) {
  if (isLoading) {
    return (
      <section>
        <h2 className="text-lg font-semibold mb-3">Top Stories</h2>
        <div
          className="flex gap-4 overflow-x-auto pb-2"
          data-testid="stories-skeleton"
        >
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="min-w-[240px] h-36 animate-pulse rounded-lg bg-gray-100"
            />
          ))}
        </div>
      </section>
    );
  }

  if (stories.length === 0) {
    return (
      <section>
        <h2 className="text-lg font-semibold mb-3">Top Stories</h2>
        <p className="text-sm text-gray-500" data-testid="stories-empty">
          Stories are being analyzed &mdash; check back soon
        </p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="text-lg font-semibold mb-3">Top Stories</h2>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {stories.map((story) => (
          <StoryCard key={story.id} story={story} />
        ))}
      </div>
      <Link
        href="/stories"
        className="mt-2 inline-block text-sm text-violet-600 hover:underline"
      >
        View all stories &rarr;
      </Link>
    </section>
  );
}
