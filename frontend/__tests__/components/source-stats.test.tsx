import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SourceStats, {
  computeAvgTrust,
  computeBiasDistribution,
} from "@/components/sources/SourceStats";
import { makeSource, makeSourceList } from "../helpers/fixtures";

describe("computeAvgTrust", () => {
  it("returns 0 for empty array", () => {
    expect(computeAvgTrust([])).toBe(0);
  });

  it("computes average for single source", () => {
    const sources = [makeSource({ trust_score: 0.8 })];
    expect(computeAvgTrust(sources)).toBeCloseTo(0.8);
  });

  it("computes average for multiple sources", () => {
    const sources = [
      makeSource({ trust_score: 0.9 }),
      makeSource({ trust_score: 0.6 }),
      makeSource({ trust_score: 0.3 }),
    ];
    expect(computeAvgTrust(sources)).toBeCloseTo(0.6);
  });
});

describe("computeBiasDistribution", () => {
  it("returns empty object for empty array", () => {
    expect(computeBiasDistribution([])).toEqual({});
  });

  it("counts bias labels correctly", () => {
    const sources = [
      makeSource({ bias_label: "center" }),
      makeSource({ bias_label: "center" }),
      makeSource({ bias_label: "left" }),
      makeSource({ bias_label: "right" }),
    ];
    const dist = computeBiasDistribution(sources);
    expect(dist.center).toBe(2);
    expect(dist.left).toBe(1);
    expect(dist.right).toBe(1);
  });

  it("handles all bias labels from makeSourceList", () => {
    const sources = makeSourceList();
    const dist = computeBiasDistribution(sources);
    // 10 sources: center=2, center_left=3, right=2, left=2, center_right=1
    expect(dist.center).toBe(2);
    expect(dist.center_left).toBe(3);
    expect(dist.right).toBe(2);
    expect(dist.left).toBe(2);
    expect(dist.center_right).toBe(1);
  });
});

describe("SourceStats", () => {
  it("renders average trust score", () => {
    const sources = makeSourceList();
    render(<SourceStats sources={sources} />);
    const avgCard = screen.getByTestId("stat-avg-trust");
    // Average of all 10 sources
    const avg = computeAvgTrust(sources);
    expect(avgCard).toHaveTextContent(avg.toFixed(2));
  });

  it("renders total active count", () => {
    const sources = makeSourceList();
    render(<SourceStats sources={sources} />);
    const totalCard = screen.getByTestId("stat-total-active");
    expect(totalCard).toHaveTextContent("10");
  });

  it("renders bias distribution chart", () => {
    const sources = makeSourceList();
    render(<SourceStats sources={sources} />);
    expect(screen.getByTestId("stat-bias-distribution")).toBeInTheDocument();
    expect(screen.getByTestId("bias-distribution-chart")).toBeInTheDocument();
  });

  it("renders the stats grid container", () => {
    render(<SourceStats sources={makeSourceList()} />);
    expect(screen.getByTestId("source-stats")).toBeInTheDocument();
  });

  it("renders labels for each stat", () => {
    render(<SourceStats sources={makeSourceList()} />);
    expect(screen.getByText("Average Trust")).toBeInTheDocument();
    expect(screen.getByText("Bias Distribution")).toBeInTheDocument();
    expect(screen.getByText("Total Active")).toBeInTheDocument();
  });

  it("shows 0.00 for empty sources", () => {
    render(<SourceStats sources={[]} />);
    expect(screen.getByTestId("stat-avg-trust")).toHaveTextContent("0.00");
    expect(screen.getByTestId("stat-total-active")).toHaveTextContent("0");
  });

  it("shows No data in chart for empty sources", () => {
    render(<SourceStats sources={[]} />);
    expect(screen.getByTestId("bias-chart-empty")).toBeInTheDocument();
  });
});
