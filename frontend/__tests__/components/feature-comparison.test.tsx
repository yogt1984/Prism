import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FeatureComparison, {
  FEATURES,
} from "@/components/settings/FeatureComparison";

describe("FeatureComparison", () => {
  it("renders the comparison table", () => {
    render(<FeatureComparison />);
    expect(screen.getByTestId("feature-comparison")).toBeInTheDocument();
  });

  it("renders all 6 feature rows", () => {
    render(<FeatureComparison />);
    expect(screen.getAllByTestId("comparison-row")).toHaveLength(6);
  });

  it("renders column headers", () => {
    render(<FeatureComparison />);
    expect(screen.getByText("Feature")).toBeInTheDocument();
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("Pro ($7/mo)")).toBeInTheDocument();
  });

  it("renders Topics row", () => {
    render(<FeatureComparison />);
    expect(screen.getByText("Topics")).toBeInTheDocument();
    expect(screen.getByText("All 8")).toBeInTheDocument();
  });

  it("renders Stories/briefing row", () => {
    render(<FeatureComparison />);
    expect(screen.getByText("Stories/briefing")).toBeInTheDocument();
    expect(screen.getByText("Up to 25")).toBeInTheDocument();
  });

  it("renders Formats row", () => {
    render(<FeatureComparison />);
    expect(screen.getByText("Formats")).toBeInTheDocument();
    expect(screen.getByText("All 3")).toBeInTheDocument();
  });

  it("renders API Access row", () => {
    render(<FeatureComparison />);
    expect(screen.getByText("API Access")).toBeInTheDocument();
  });

  it("FEATURES constant has 6 items", () => {
    expect(FEATURES).toHaveLength(6);
  });

  it("each feature has feature, free, and pro keys", () => {
    FEATURES.forEach((f) => {
      expect(f.feature).toBeTruthy();
      expect(f.free).toBeTruthy();
      expect(f.pro).toBeTruthy();
    });
  });
});
