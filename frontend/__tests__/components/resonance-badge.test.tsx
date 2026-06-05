import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ResonanceBadge, {
  getResonanceLevel,
  getMomentumArrow,
} from "@/components/dashboard/ResonanceBadge";

describe("getResonanceLevel", () => {
  it("returns Low for score 0", () => {
    expect(getResonanceLevel(0)).toEqual({
      color: "bg-gray-100 text-gray-600",
      label: "Low",
    });
  });

  it("returns Low for score 0.9", () => {
    expect(getResonanceLevel(0.9).label).toBe("Low");
  });

  it("returns Moderate for score 1.0", () => {
    expect(getResonanceLevel(1.0).label).toBe("Moderate");
  });

  it("returns Moderate for score 2.5", () => {
    const result = getResonanceLevel(2.5);
    expect(result.label).toBe("Moderate");
    expect(result.color).toContain("blue");
  });

  it("returns High for score 3.0", () => {
    expect(getResonanceLevel(3.0).label).toBe("High");
  });

  it("returns High for score 4.9", () => {
    const result = getResonanceLevel(4.9);
    expect(result.label).toBe("High");
    expect(result.color).toContain("orange");
  });

  it("returns Viral for score 5.0", () => {
    expect(getResonanceLevel(5.0).label).toBe("Viral");
  });

  it("returns Viral for score 10.0", () => {
    const result = getResonanceLevel(10.0);
    expect(result.label).toBe("Viral");
    expect(result.color).toContain("red");
  });
});

describe("getMomentumArrow", () => {
  it("returns flat arrow for undefined momentum", () => {
    expect(getMomentumArrow(undefined)).toBe("\u2500");
  });

  it("returns flat arrow for zero momentum", () => {
    expect(getMomentumArrow(0)).toBe("\u2500");
  });

  it("returns flat arrow for small positive momentum", () => {
    expect(getMomentumArrow(0.05)).toBe("\u2500");
  });

  it("returns flat arrow for small negative momentum", () => {
    expect(getMomentumArrow(-0.09)).toBe("\u2500");
  });

  it("returns up arrow for positive momentum", () => {
    expect(getMomentumArrow(0.5)).toBe("\u25B2");
  });

  it("returns down arrow for negative momentum", () => {
    expect(getMomentumArrow(-0.3)).toBe("\u25BC");
  });

  it("returns up arrow at threshold 0.1", () => {
    expect(getMomentumArrow(0.1)).toBe("\u25B2");
  });

  it("returns down arrow at threshold -0.1", () => {
    expect(getMomentumArrow(-0.1)).toBe("\u25BC");
  });
});

describe("ResonanceBadge", () => {
  it("renders score with one decimal", () => {
    render(<ResonanceBadge score={4.72} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("4.7");
  });

  it("renders Low label for low score", () => {
    render(<ResonanceBadge score={0.5} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("Low");
  });

  it("renders Moderate label", () => {
    render(<ResonanceBadge score={2.0} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("Moderate");
  });

  it("renders High label", () => {
    render(<ResonanceBadge score={3.5} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("High");
  });

  it("renders Viral label", () => {
    render(<ResonanceBadge score={7.0} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("Viral");
  });

  it("renders up arrow with positive momentum", () => {
    render(<ResonanceBadge score={3.0} momentum={0.5} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("\u25B2");
  });

  it("renders down arrow with negative momentum", () => {
    render(<ResonanceBadge score={3.0} momentum={-0.3} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("\u25BC");
  });

  it("renders flat arrow with no momentum", () => {
    render(<ResonanceBadge score={3.0} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("\u2500");
  });

  it("renders as inline-flex span", () => {
    render(<ResonanceBadge score={3.0} />);
    const badge = screen.getByTestId("resonance-badge");
    expect(badge.tagName).toBe("SPAN");
  });
});
