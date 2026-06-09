import type { Source } from "@/lib/types";

export default function LifecycleInfo({ source }: { source: Source }) {
  if (source.status === "candidate") {
    return (
      <span className="text-xs text-gray-500 tabular-nums" data-testid="lifecycle-info">
        {source.sighting_count} sighting{source.sighting_count !== 1 ? "s" : ""}
      </span>
    );
  }

  if (source.status === "probation") {
    const total = source.articles_validated + source.articles_failed;
    return (
      <span className="text-xs text-gray-500 tabular-nums" data-testid="lifecycle-info">
        {source.articles_validated}/{total} validated
      </span>
    );
  }

  return null;
}
