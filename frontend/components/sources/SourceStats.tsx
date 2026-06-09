import type { Source, SourceStatus } from "@/lib/types";
import BiasDistributionChart from "./BiasDistributionChart";
import StatusBadge from "./StatusBadge";
import Card from "@/components/ui/Card";

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

export function computeStatusDistribution(
  sources: Source[],
): Record<string, number> {
  return sources.reduce(
    (acc, s) => {
      acc[s.status] = (acc[s.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
}

export default function SourceStats({ sources }: SourceStatsProps) {
  const avgTrust = computeAvgTrust(sources);
  const biasDistribution = computeBiasDistribution(sources);
  const statusDistribution = computeStatusDistribution(sources);
  const statusEntries = Object.entries(statusDistribution).filter(
    ([, count]) => count > 0,
  );

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      data-testid="source-stats"
    >
      <Card data-testid="stat-avg-trust">
        <p className="text-xs text-gray-500 uppercase tracking-wide">
          Average Trust
        </p>
        <p className="mt-1 text-2xl font-semibold text-gray-900">
          {avgTrust.toFixed(2)}
        </p>
      </Card>

      <Card data-testid="stat-bias-distribution">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">
          Bias Distribution
        </p>
        <BiasDistributionChart distribution={biasDistribution} />
      </Card>

      <Card data-testid="stat-total-sources">
        <p className="text-xs text-gray-500 uppercase tracking-wide">
          Total Sources
        </p>
        <p className="mt-1 text-2xl font-semibold text-gray-900">
          {sources.length}
        </p>
      </Card>

      <Card data-testid="stat-status-breakdown">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">
          Lifecycle Breakdown
        </p>
        <ul className="space-y-1">
          {statusEntries.map(([status, count]) => (
            <li key={status} className="flex items-center justify-between">
              <StatusBadge status={status as SourceStatus} />
              <span className="text-sm text-gray-700 tabular-nums font-medium">
                {count}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
