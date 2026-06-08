import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BiasDistributionChart, {
  BIAS_COLORS,
  BIAS_LABELS,
} from "@/components/sources/BiasDistributionChart";

describe("BiasDistributionChart", () => {
  const distribution = {
    center: 5,
    left: 2,
    right: 3,
    center_left: 4,
    center_right: 1,
  };

  it("renders the chart container", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    expect(screen.getByTestId("bias-distribution-chart")).toBeInTheDocument();
  });

  it("renders donut segments for each bias label", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    expect(screen.getByTestId("donut-segment-center")).toBeInTheDocument();
    expect(screen.getByTestId("donut-segment-left")).toBeInTheDocument();
    expect(screen.getByTestId("donut-segment-right")).toBeInTheDocument();
    expect(screen.getByTestId("donut-segment-center_left")).toBeInTheDocument();
    expect(screen.getByTestId("donut-segment-center_right")).toBeInTheDocument();
  });

  it("applies correct stroke colors to segments", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    const leftSeg = screen.getByTestId("donut-segment-left");
    expect(leftSeg).toHaveAttribute("stroke", BIAS_COLORS.left);
  });

  it("renders legend with label names and counts", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    expect(screen.getByText("Center")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Left")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Right")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders empty state when total is 0", () => {
    render(<BiasDistributionChart distribution={{}} />);
    expect(screen.getByTestId("bias-chart-empty")).toHaveTextContent("No data");
  });

  it("renders empty state when all counts are 0", () => {
    render(
      <BiasDistributionChart
        distribution={{ center: 0, left: 0, right: 0 }}
      />,
    );
    expect(screen.getByTestId("bias-chart-empty")).toBeInTheDocument();
  });

  it("does not render segments for zero-count entries", () => {
    render(
      <BiasDistributionChart distribution={{ center: 5, left: 0 }} />,
    );
    expect(screen.getByTestId("donut-segment-center")).toBeInTheDocument();
    expect(screen.queryByTestId("donut-segment-left")).toBeNull();
  });

  it("renders an SVG element", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    const svg = screen
      .getByTestId("bias-distribution-chart")
      .querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("handles single-bias distribution", () => {
    render(<BiasDistributionChart distribution={{ center: 10 }} />);
    expect(screen.getByTestId("donut-segment-center")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("exports BIAS_COLORS with all 6 labels", () => {
    expect(Object.keys(BIAS_COLORS)).toHaveLength(6);
    expect(BIAS_COLORS.left).toBeDefined();
    expect(BIAS_COLORS.center).toBeDefined();
    expect(BIAS_COLORS.right).toBeDefined();
    expect(BIAS_COLORS.center_left).toBeDefined();
    expect(BIAS_COLORS.center_right).toBeDefined();
    expect(BIAS_COLORS.unknown).toBeDefined();
  });

  it("exports BIAS_LABELS with human-readable names", () => {
    expect(BIAS_LABELS.left).toBe("Left");
    expect(BIAS_LABELS.center_left).toBe("Center-Left");
    expect(BIAS_LABELS.center).toBe("Center");
    expect(BIAS_LABELS.center_right).toBe("Center-Right");
    expect(BIAS_LABELS.right).toBe("Right");
    expect(BIAS_LABELS.unknown).toBe("Unknown");
  });

  it("uses circle elements for donut rendering", () => {
    render(<BiasDistributionChart distribution={distribution} />);
    const svg = screen
      .getByTestId("bias-distribution-chart")
      .querySelector("svg");
    const circles = svg?.querySelectorAll("circle");
    expect(circles).toHaveLength(5); // 5 non-zero entries
  });
});
