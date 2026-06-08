import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { makePerceptionHistory } from "../helpers/fixtures";

// Mock recharts - it doesn't render in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children, data }: { children: React.ReactNode; data: unknown[] }) => (
    <div data-testid="line-chart" data-count={data.length}>
      {children}
    </div>
  ),
  Line: ({ stroke, dataKey }: { stroke: string; dataKey: string }) => (
    <div data-testid={`line-${dataKey}`} data-stroke={stroke} />
  ),
  ReferenceLine: ({ y }: { y: number }) => (
    <div data-testid="reference-line" data-y={y} />
  ),
}));

import MiniChart, { getStrokeColor } from "@/components/perception/MiniChart";

describe("getStrokeColor", () => {
  it("returns green for positive momentum", () => {
    expect(getStrokeColor(0.15)).toBe("#22C55E");
  });

  it("returns red for negative momentum", () => {
    expect(getStrokeColor(-0.1)).toBe("#EF4444");
  });

  it("returns gray for zero momentum", () => {
    expect(getStrokeColor(0)).toBe("#9CA3AF");
  });
});

describe("MiniChart", () => {
  it("renders empty state when no data", () => {
    render(<MiniChart data={[]} momentum={0} />);
    expect(screen.getByTestId("mini-chart-empty")).toHaveTextContent(
      "No data yet",
    );
  });

  it("renders chart with data", () => {
    const data = makePerceptionHistory(10);
    render(<MiniChart data={data} momentum={0.1} />);
    expect(screen.getByTestId("mini-chart")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("passes reversed data to LineChart", () => {
    const data = makePerceptionHistory(5);
    render(<MiniChart data={data} momentum={0} />);
    const chart = screen.getByTestId("line-chart");
    expect(chart).toHaveAttribute("data-count", "5");
  });

  it("renders perception line with correct color for positive momentum", () => {
    render(<MiniChart data={makePerceptionHistory(5)} momentum={0.1} />);
    const line = screen.getByTestId("line-perception");
    expect(line).toHaveAttribute("data-stroke", "#22C55E");
  });

  it("renders perception line with red for negative momentum", () => {
    render(<MiniChart data={makePerceptionHistory(5)} momentum={-0.1} />);
    const line = screen.getByTestId("line-perception");
    expect(line).toHaveAttribute("data-stroke", "#EF4444");
  });

  it("renders perception line with gray for zero momentum", () => {
    render(<MiniChart data={makePerceptionHistory(5)} momentum={0} />);
    const line = screen.getByTestId("line-perception");
    expect(line).toHaveAttribute("data-stroke", "#9CA3AF");
  });

  it("renders reference line at y=0", () => {
    render(<MiniChart data={makePerceptionHistory(5)} momentum={0} />);
    expect(screen.getByTestId("reference-line")).toHaveAttribute(
      "data-y",
      "0",
    );
  });

  it("has mini-chart test id container", () => {
    render(<MiniChart data={makePerceptionHistory(3)} momentum={0} />);
    expect(screen.getByTestId("mini-chart")).toBeInTheDocument();
  });
});
