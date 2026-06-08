"use client";

import type { Keyword, PerceptionSnapshot } from "@/lib/types";
import CategoryPill from "@/components/dashboard/CategoryPill";
import MomentumArrow from "./MomentumArrow";
import MiniChart from "./MiniChart";

interface KeywordOverviewCardProps {
  keyword: Keyword;
  latest: PerceptionSnapshot | null;
  history: PerceptionSnapshot[];
  isHistoryLoading: boolean;
  onExpand: () => void;
  onRemove: () => void;
}

export default function KeywordOverviewCard({
  keyword,
  latest,
  history,
  isHistoryLoading,
  onExpand,
  onRemove,
}: KeywordOverviewCardProps) {
  return (
    <div
      className="rounded-lg border border-gray-200 p-4 space-y-3 hover:border-gray-300 transition-colors"
      data-testid={`keyword-card-${keyword.id}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h3
            className="font-semibold text-gray-900"
            data-testid="keyword-name"
          >
            {keyword.keyword}
          </h3>
          {keyword.category && (
            <CategoryPill category={keyword.category} />
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="text-gray-400 hover:text-red-500 text-sm"
          data-testid="remove-keyword-btn"
          title="Remove keyword"
        >
          &times;
        </button>
      </div>

      {/* Perception value */}
      {latest ? (
        <>
          <div className="flex items-baseline gap-2">
            <span
              className="text-2xl font-bold text-gray-900 tabular-nums"
              data-testid="perception-value"
            >
              {latest.perception.toFixed(2)}
            </span>
            <MomentumArrow value={latest.momentum} />
            <span className="text-xs text-gray-400">perception pressure</span>
          </div>

          {/* Stat row */}
          <div
            className="grid grid-cols-4 gap-2 text-center"
            data-testid="stat-row"
          >
            <div>
              <p className="text-sm font-medium text-gray-900 tabular-nums">
                {latest.salience.toFixed(1)}
              </p>
              <p className="text-xs text-gray-400">salience</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 tabular-nums">
                {latest.valence >= 0 ? "+" : ""}
                {latest.valence.toFixed(2)}
              </p>
              <p className="text-xs text-gray-400">valence</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 tabular-nums">
                {latest.source_count}
              </p>
              <p className="text-xs text-gray-400">sources</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 tabular-nums">
                {latest.cluster_count}
              </p>
              <p className="text-xs text-gray-400">clusters</p>
            </div>
          </div>
        </>
      ) : (
        <p
          className="text-sm text-gray-400 py-4"
          data-testid="waiting-message"
        >
          Waiting for first scan...
        </p>
      )}

      {/* Mini chart */}
      {isHistoryLoading ? (
        <div className="h-20 bg-gray-50 rounded animate-pulse" />
      ) : (
        <MiniChart data={history} momentum={latest?.momentum ?? 0} />
      )}

      {/* Expand */}
      <button
        type="button"
        onClick={onExpand}
        className="w-full text-center text-sm text-violet-600 hover:underline py-1"
        data-testid="expand-btn"
      >
        View details
      </button>
    </div>
  );
}
