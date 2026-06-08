import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MomentumIndicator from "@/components/perception/MomentumIndicator";

describe("MomentumIndicator", () => {
  it("renders Rising label for positive momentum", () => {
    render(<MomentumIndicator momentum={0.12} />);
    expect(screen.getByTestId("trend-label")).toHaveTextContent("Rising");
  });

  it("renders Falling label for negative momentum", () => {
    render(<MomentumIndicator momentum={-0.08} />);
    expect(screen.getByTestId("trend-label")).toHaveTextContent("Falling");
  });

  it("renders Stable label for near-zero momentum", () => {
    render(<MomentumIndicator momentum={0.005} />);
    expect(screen.getByTestId("trend-label")).toHaveTextContent("Stable");
  });

  it("shows positive shift in explanation", () => {
    render(<MomentumIndicator momentum={0.12} />);
    expect(screen.getByTestId("trend-explanation")).toHaveTextContent(
      "Perception shifted +0.12 in last scan",
    );
  });

  it("shows negative shift in explanation", () => {
    render(<MomentumIndicator momentum={-0.05} />);
    expect(screen.getByTestId("trend-explanation")).toHaveTextContent(
      "Perception shifted -0.05 in last scan",
    );
  });

  it("shows zero shift with + prefix", () => {
    render(<MomentumIndicator momentum={0} />);
    expect(screen.getByTestId("trend-explanation")).toHaveTextContent(
      "Perception shifted +0.00 in last scan",
    );
  });

  it("renders momentum arrow", () => {
    render(<MomentumIndicator momentum={0.12} />);
    expect(screen.getByTestId("momentum-arrow")).toBeInTheDocument();
  });

  it("has correct container test id", () => {
    render(<MomentumIndicator momentum={0} />);
    expect(screen.getByTestId("momentum-indicator")).toBeInTheDocument();
  });
});
