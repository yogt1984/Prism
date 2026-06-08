import type { BiasLabel } from "@/lib/types";

const BIAS_COLORS: Record<BiasLabel, string> = {
  left: "#2563eb",       // blue-600
  center_left: "#93c5fd", // blue-300
  center: "#9ca3af",     // gray-400
  center_right: "#fca5a5", // red-300
  right: "#dc2626",      // red-600
  unknown: "#e5e7eb",    // gray-200
};

const BIAS_LABELS: Record<BiasLabel, string> = {
  left: "Left",
  center_left: "Center-Left",
  center: "Center",
  center_right: "Center-Right",
  right: "Right",
  unknown: "Unknown",
};

interface BiasDistributionChartProps {
  distribution: Record<string, number>;
}

export default function BiasDistributionChart({
  distribution,
}: BiasDistributionChartProps) {
  const entries = Object.entries(distribution).filter(([, count]) => count > 0);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  if (total === 0) {
    return (
      <p className="text-sm text-gray-400" data-testid="bias-chart-empty">
        No data
      </p>
    );
  }

  // Build SVG donut segments
  const radius = 40;
  const cx = 50;
  const cy = 50;
  const strokeWidth = 16;
  const circumference = 2 * Math.PI * radius;
  let cumulativeOffset = 0;

  const segments = entries.map(([label, count]) => {
    const fraction = count / total;
    const dashLength = fraction * circumference;
    const dashOffset = -cumulativeOffset;
    cumulativeOffset += dashLength;

    return (
      <circle
        key={label}
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke={BIAS_COLORS[label as BiasLabel] ?? BIAS_COLORS.unknown}
        strokeWidth={strokeWidth}
        strokeDasharray={`${dashLength} ${circumference - dashLength}`}
        strokeDashoffset={dashOffset}
        data-testid={`donut-segment-${label}`}
      />
    );
  });

  return (
    <div className="flex items-center gap-4" data-testid="bias-distribution-chart">
      <svg viewBox="0 0 100 100" className="w-20 h-20" aria-hidden="true">
        {segments}
      </svg>
      <ul className="space-y-1">
        {entries.map(([label, count]) => (
          <li key={label} className="flex items-center gap-2 text-xs text-gray-600">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{
                backgroundColor:
                  BIAS_COLORS[label as BiasLabel] ?? BIAS_COLORS.unknown,
              }}
            />
            <span>{BIAS_LABELS[label as BiasLabel] ?? label}</span>
            <span className="text-gray-400">{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export { BIAS_COLORS, BIAS_LABELS };
