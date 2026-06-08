import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import QualityIndicator, {
  getQualityLevel,
} from "@/components/story/QualityIndicator";

describe("QualityIndicator", () => {
  it('shows "High quality" for score >= 0.8', () => {
    render(<QualityIndicator score={0.85} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "High quality",
    );
  });

  it("applies green color for high quality", () => {
    render(<QualityIndicator score={0.9} />);
    expect(screen.getByTestId("quality-indicator").className).toContain(
      "text-green-600",
    );
  });

  it('shows "Medium quality" for 0.5 <= score < 0.8', () => {
    render(<QualityIndicator score={0.6} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "Medium quality",
    );
  });

  it("applies yellow color for medium quality", () => {
    render(<QualityIndicator score={0.5} />);
    expect(screen.getByTestId("quality-indicator").className).toContain(
      "text-yellow-600",
    );
  });

  it('shows "Low quality" for score < 0.5', () => {
    render(<QualityIndicator score={0.3} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "Low quality",
    );
  });

  it("applies red color for low quality", () => {
    render(<QualityIndicator score={0.2} />);
    expect(screen.getByTestId("quality-indicator").className).toContain(
      "text-red-600",
    );
  });

  it("includes percentage in title", () => {
    render(<QualityIndicator score={0.85} />);
    expect(screen.getByTestId("quality-indicator")).toHaveAttribute(
      "title",
      "Quality: 85%",
    );
  });

  it("rounds percentage correctly in title", () => {
    render(<QualityIndicator score={0.777} />);
    expect(screen.getByTestId("quality-indicator")).toHaveAttribute(
      "title",
      "Quality: 78%",
    );
  });

  it("handles boundary at 0.8 as High", () => {
    render(<QualityIndicator score={0.8} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "High quality",
    );
  });

  it("handles boundary at 0.5 as Medium", () => {
    render(<QualityIndicator score={0.5} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "Medium quality",
    );
  });

  it("handles score of 0 as Low", () => {
    render(<QualityIndicator score={0} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "Low quality",
    );
  });

  it("handles score of 1.0 as High", () => {
    render(<QualityIndicator score={1.0} />);
    expect(screen.getByTestId("quality-indicator")).toHaveTextContent(
      "High quality",
    );
  });
});

describe("getQualityLevel", () => {
  it("returns High/green for 0.8", () => {
    expect(getQualityLevel(0.8)).toEqual({
      color: "text-green-600",
      label: "High",
    });
  });

  it("returns Medium/yellow for 0.5", () => {
    expect(getQualityLevel(0.5)).toEqual({
      color: "text-yellow-600",
      label: "Medium",
    });
  });

  it("returns Low/red for 0.49", () => {
    expect(getQualityLevel(0.49)).toEqual({
      color: "text-red-600",
      label: "Low",
    });
  });
});
