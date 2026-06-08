"use client";

import { useState } from "react";
import type { Keyword, PerceptionSnapshot } from "@/lib/types";
import type { TimeRange } from "@/lib/hooks";
import { usePerceptionHistoryByRange, useLatestPerception } from "@/lib/hooks";
import PerceptionChart from "./PerceptionChart";
import TimeRangeSelector from "./TimeRangeSelector";
import MomentumIndicator from "./MomentumIndicator";

interface DetailPanelProps {
  keyword: Keyword;
  onClose: () => void;
}

export default function DetailPanel({
  keyword,
  onClose,
}: DetailPanelProps) {
  const { data: latest } = useLatestPerception(keyword.id);
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const {
    data: history,
    isLoading,
    isError,
    refetch,
  } = usePerceptionHistoryByRange(keyword.id, timeRange);

  const aliases = keyword.aliases
    ? keyword.aliases.split(",").map((a) => a.trim()).filter(Boolean)
    : [];

  return (
    <div
      className="rounded-lg border border-gray-200 p-6 space-y-4"
      data-testid="detail-panel"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900" data-testid="detail-keyword">
            {keyword.keyword}
          </h2>
          {aliases.length > 0 && (
            <p className="text-sm text-gray-400 mt-0.5" data-testid="detail-aliases">
              Also: {aliases.join(", ")}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            data-testid="detail-close-btn"
          >
            &times;
          </button>
        </div>
      </div>

      {/* Chart */}
      {isLoading && (
        <div
          className="h-64 bg-gray-50 rounded animate-pulse"
          data-testid="chart-loading"
        />
      )}

      {isError && (
        <div
          className="h-64 flex flex-col items-center justify-center gap-2"
          data-testid="chart-error"
        >
          <p className="text-sm text-gray-600">Could not load history</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="text-sm text-violet-600 hover:underline"
            data-testid="chart-retry-btn"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && (
        <PerceptionChart data={history ?? []} timeRange={timeRange} />
      )}

      {/* Momentum */}
      {latest && <MomentumIndicator momentum={latest.momentum} />}
    </div>
  );
}
