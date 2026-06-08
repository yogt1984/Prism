"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type { PerceptionSnapshot } from "@/lib/types";
import type { TimeRange } from "@/lib/hooks";

interface ChartDataPoint {
  time: number;
  perception: number;
  valence: number;
  salience: number;
  source_count: number;
  cluster_count: number;
}

interface PerceptionChartProps {
  data: PerceptionSnapshot[];
  timeRange: TimeRange;
}

export function toChartData(snapshots: PerceptionSnapshot[]): ChartDataPoint[] {
  return [...snapshots].reverse().map((s) => ({
    time: new Date(s.computed_at).getTime(),
    perception: s.perception,
    valence: s.valence,
    salience: s.salience,
    source_count: s.source_count,
    cluster_count: s.cluster_count,
  }));
}

function formatXAxis(timestamp: number, timeRange: TimeRange): string {
  const d = new Date(timestamp);
  if (timeRange === "30d") {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  if (timeRange === "24h") {
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  // 7d
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="bg-white border border-gray-200 rounded-lg shadow-sm p-3 text-xs space-y-1"
      data-testid="chart-tooltip"
    >
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-4">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-mono">{entry.value.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

export default function PerceptionChart({
  data,
  timeRange,
}: PerceptionChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="h-64 flex items-center justify-center text-sm text-gray-400"
        data-testid="chart-empty"
      >
        No data for this time range
      </div>
    );
  }

  const chartData = toChartData(data);

  return (
    <div data-testid="perception-chart" className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
          <XAxis
            dataKey="time"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v) => formatXAxis(v, timeRange)}
            tick={{ fontSize: 11 }}
            scale="time"
          />
          <YAxis
            yAxisId="left"
            domain={[-1, 1]}
            tick={{ fontSize: 11 }}
            label={{
              value: "Perception / Valence",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 10, fill: "#6B7280" },
            }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 11 }}
            label={{
              value: "Salience",
              angle: 90,
              position: "insideRight",
              style: { fontSize: 10, fill: "#6B7280" },
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            yAxisId="left"
            y={0}
            stroke="#D1D5DB"
            strokeDasharray="4 4"
          />
          <Bar
            dataKey="salience"
            yAxisId="right"
            fill="#9CA3AF"
            opacity={0.3}
            name="salience"
            isAnimationActive={false}
          />
          <Line
            dataKey="perception"
            yAxisId="left"
            stroke="#8B5CF6"
            strokeWidth={2}
            dot={false}
            name="perception"
            isAnimationActive={false}
          />
          <Line
            dataKey="valence"
            yAxisId="left"
            stroke="#3B82F6"
            strokeWidth={1}
            strokeDasharray="4 4"
            dot={false}
            name="valence"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
