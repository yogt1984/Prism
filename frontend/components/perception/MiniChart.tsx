"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine,
} from "recharts";
import type { PerceptionSnapshot } from "@/lib/types";

interface MiniChartProps {
  data: PerceptionSnapshot[];
  momentum: number;
}

function getStrokeColor(momentum: number): string {
  if (momentum > 0) return "#22C55E"; // green-500
  if (momentum < 0) return "#EF4444"; // red-500
  return "#9CA3AF"; // gray-400
}

export default function MiniChart({ data, momentum }: MiniChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="h-20 flex items-center justify-center text-xs text-gray-400"
        data-testid="mini-chart-empty"
      >
        No data yet
      </div>
    );
  }

  const reversed = [...data].reverse();

  return (
    <div data-testid="mini-chart" className="h-20">
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={reversed}>
          <Line
            dataKey="perception"
            stroke={getStrokeColor(momentum)}
            dot={false}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
          <ReferenceLine y={0} stroke="#E5E7EB" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export { getStrokeColor };
