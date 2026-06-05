"use client";

import { useActiveKeywords, usePerceptionHistory } from "@/lib/hooks";
import KeywordItem from "./KeywordItem";
import type { Keyword } from "@/lib/types";

function KeywordItemWithHistory({ kw }: { kw: Keyword }) {
  const { data: history = [], isLoading } = usePerceptionHistory(kw.id);
  return (
    <KeywordItem keyword={kw.keyword} history={history} isLoading={isLoading} />
  );
}

export default function KeywordSidebar() {
  const { data: keywords = [], isLoading } = useActiveKeywords();

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="keywords-skeleton">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-8 animate-pulse rounded bg-gray-200" />
        ))}
      </div>
    );
  }

  if (keywords.length === 0) {
    return (
      <div className="text-center py-4" data-testid="keywords-empty">
        <p className="text-sm text-gray-500 mb-2">
          Track your first keyword to see media pressure
        </p>
        <button className="text-sm font-medium text-violet-600 hover:underline">
          + Add keyword
        </button>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Tracked Keywords
      </h3>
      <div className="space-y-1">
        {keywords.map((kw) => (
          <KeywordItemWithHistory key={kw.id} kw={kw} />
        ))}
      </div>
    </div>
  );
}
