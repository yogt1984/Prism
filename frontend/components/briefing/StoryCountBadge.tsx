import Badge from "@/components/ui/Badge";

export default function StoryCountBadge({ count }: { count: number }) {
  return (
    <Badge
      color="bg-violet-100 text-violet-700"
      className="gap-1"
      data-testid="story-count-badge"
    >
      {count} {count === 1 ? "story" : "stories"}
    </Badge>
  );
}
