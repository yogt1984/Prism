import type { Source } from "@/lib/types";
import BiasDistributionChart from "./BiasDistributionChart";

interface SourceStatsProps {
  sources: Source[];
}

export function computeAvgTrust(sources: Source[]): number {
  if (sources.length === 0) return 0;
  const sum = sources.reduce((acc, s) => acc + s.trust_score, 0);
  return sum / sources.length;
}

export function computeBiasDistribution(
  sources: Source[],
): Record<string, number> {
  return sources.reduce(
    (acc, s) => {
      acc[s.bias_label] = (acc[s.bias_label] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
}

export default function SourceStats({ sources }: SourceStatsProps) {
  const avgTrust = computeAvgTrust(sources);
  const distribution = computeBiasDistribution(sources);

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-3 gap-4"
      data-testid="source-stats"
    >
      <div className="rounded-lg border border-gray-200 p-4" data-testid="stat-avg-trust">
        <p className="text-xs text-gray-500 uppercase tracking-wide">
          Average Trust
        </p>
        <p className="mt-1 text-2xl font-semibold text-gray-900">
          {avgTrust.toFixed(2)}
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 p-4" data-testid="stat-bias-distribution">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">
          Bias Distribution
        </p>
        <BiasDistributionChart distribution={distribution} />
      </div>

      <div className="rounded-lg border border-gray-200 p-4" data-testid="stat-total-active">
        <p className="text-xs text-gray-500 uppercase tracking-wide">
          Total Active
        </p>
        <p className="mt-1 text-2xl font-semibold text-gray-900">
          {sources.length}
        </p>
      </div>
    </div>
  );
}
