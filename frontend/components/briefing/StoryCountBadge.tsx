export default function StoryCountBadge({ count }: { count: number }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-violet-100 text-violet-700"
      data-testid="story-count-badge"
    >
      {count} {count === 1 ? "story" : "stories"}
    </span>
  );
}
