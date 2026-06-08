import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { makePerceptionHistory } from "../helpers/fixtures";

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  ComposedChart: ({ children, data }: { children: React.ReactNode; data: unknown[] }) => (
    <div data-testid="composed-chart" data-count={data.length}>
      {children}
    </div>
  ),
  Line: ({ dataKey, stroke }: { dataKey: string; stroke: string }) => (
    <div data-testid={`chart-line-${dataKey}`} data-stroke={stroke} />
  ),
  Bar: ({ dataKey, fill }: { dataKey: string; fill: string }) => (
    <div data-testid={`chart-bar-${dataKey}`} data-fill={fill} />
  ),
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: ({ yAxisId }: { yAxisId?: string }) => (
    <div data-testid={`y-axis-${yAxisId ?? "default"}`} />
  ),
  Tooltip: () => <div data-testid="tooltip" />,
  ReferenceLine: ({ y }: { y: number }) => (
    <div data-testid="chart-reference-line" data-y={y} />
  ),
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
}));

import PerceptionChart, {
  toChartData,
} from "@/components/perception/PerceptionChart";

describe("toChartData", () => {
  it("reverses data to chronological order", () => {
    const history = makePerceptionHistory(5);
    // makePerceptionHistory creates newest first? Actually it creates
    // chronologically (oldest first) based on the offset.
    // The API returns newest first, so toChartData reverses it.
    const chartData = toChartData(history);
    expect(chartData).toHaveLength(5);
    // After reverse, first item should have the last item's time
    expect(chartData[0].time).toBe(
      new Date(history[history.length - 1].computed_at).getTime(),
    );
  });

  it("maps perception fields correctly", () => {
    const history = makePerceptionHistory(1);
    const chartData = toChartData(history);
    expect(chartData[0]).toHaveProperty("time");
    expect(chartData[0]).toHaveProperty("perception");
    expect(chartData[0]).toHaveProperty("valence");
    expect(chartData[0]).toHaveProperty("salience");
    expect(chartData[0]).toHaveProperty("source_count");
    expect(chartData[0]).toHaveProperty("cluster_count");
  });

  it("converts computed_at to Unix timestamp", () => {
    const history = makePerceptionHistory(1);
    const chartData = toChartData(history);
    const expected = new Date(history[0].computed_at).getTime();
    expect(chartData[0].time).toBe(expected);
  });

  it("returns empty array for empty input", () => {
    expect(toChartData([])).toEqual([]);
  });

  it("preserves all data points", () => {
    const history = makePerceptionHistory(20);
    const chartData = toChartData(history);
    expect(chartData).toHaveLength(20);
  });
});

describe("PerceptionChart", () => {
  it("renders empty state when no data", () => {
    render(<PerceptionChart data={[]} timeRange="7d" />);
    expect(screen.getByTestId("chart-empty")).toHaveTextContent(
      "No data for this time range",
    );
  });

  it("renders chart with data", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(10)} timeRange="7d" />,
    );
    expect(screen.getByTestId("perception-chart")).toBeInTheDocument();
    expect(screen.getByTestId("composed-chart")).toBeInTheDocument();
  });

  it("passes correct data count to chart", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(15)} timeRange="7d" />,
    );
    expect(screen.getByTestId("composed-chart")).toHaveAttribute(
      "data-count",
      "15",
    );
  });

  it("renders perception line with purple stroke", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    const line = screen.getByTestId("chart-line-perception");
    expect(line).toHaveAttribute("data-stroke", "#8B5CF6");
  });

  it("renders valence line with blue stroke", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    const line = screen.getByTestId("chart-line-valence");
    expect(line).toHaveAttribute("data-stroke", "#3B82F6");
  });

  it("renders salience bar with gray fill", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    const bar = screen.getByTestId("chart-bar-salience");
    expect(bar).toHaveAttribute("data-fill", "#9CA3AF");
  });

  it("renders zero reference line", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    expect(screen.getByTestId("chart-reference-line")).toHaveAttribute(
      "data-y",
      "0",
    );
  });

  it("renders both Y axes", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    expect(screen.getByTestId("y-axis-left")).toBeInTheDocument();
    expect(screen.getByTestId("y-axis-right")).toBeInTheDocument();
  });

  it("renders X axis", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    expect(screen.getByTestId("x-axis")).toBeInTheDocument();
  });

  it("renders tooltip", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    expect(screen.getByTestId("tooltip")).toBeInTheDocument();
  });

  it("renders cartesian grid", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(5)} timeRange="7d" />,
    );
    expect(screen.getByTestId("cartesian-grid")).toBeInTheDocument();
  });

  it("has perception-chart test id", () => {
    render(
      <PerceptionChart data={makePerceptionHistory(3)} timeRange="24h" />,
    );
    expect(screen.getByTestId("perception-chart")).toBeInTheDocument();
  });
});
