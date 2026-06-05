import Sparkline from "./Sparkline";
import MomentumArrow from "./MomentumArrow";
import type { PerceptionSnapshot } from "@/lib/types";

interface KeywordItemProps {
  keyword: string;
  history: PerceptionSnapshot[];
  isLoading: boolean;
}

export default function KeywordItem({
  keyword,
  history,
  isLoading,
}: KeywordItemProps) {
  const latest = history[history.length - 1];

  return (
    <div className="flex items-center gap-2 py-1.5" data-testid="keyword-item">
      <span className="text-sm font-medium flex-1 truncate">{keyword}</span>
      {isLoading ? (
        <div
          className="w-20 h-6 animate-pulse rounded bg-gray-200"
          data-testid="keyword-skeleton"
        />
      ) : (
        <>
          <Sparkline data={history} momentum={latest?.momentum} />
          {latest && <MomentumArrow momentum={latest.momentum} />}
        </>
      )}
    </div>
  );
}
