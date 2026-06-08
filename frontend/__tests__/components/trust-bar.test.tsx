import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TrustBar, {
  getTrustColor,
  getTrustLabel,
} from "@/components/sources/TrustBar";

describe("getTrustColor", () => {
  it("returns red-400 for scores below 0.3", () => {
    expect(getTrustColor(0)).toBe("bg-red-400");
    expect(getTrustColor(0.1)).toBe("bg-red-400");
    expect(getTrustColor(0.29)).toBe("bg-red-400");
  });

  it("returns yellow-400 for scores 0.3 to 0.6", () => {
    expect(getTrustColor(0.3)).toBe("bg-yellow-400");
    expect(getTrustColor(0.45)).toBe("bg-yellow-400");
    expect(getTrustColor(0.59)).toBe("bg-yellow-400");
  });

  it("returns green-400 for scores 0.6 to 0.8", () => {
    expect(getTrustColor(0.6)).toBe("bg-green-400");
    expect(getTrustColor(0.7)).toBe("bg-green-400");
    expect(getTrustColor(0.79)).toBe("bg-green-400");
  });

  it("returns green-600 for scores 0.8 to 1.0", () => {
    expect(getTrustColor(0.8)).toBe("bg-green-600");
    expect(getTrustColor(0.92)).toBe("bg-green-600");
    expect(getTrustColor(1.0)).toBe("bg-green-600");
  });
});

describe("getTrustLabel", () => {
  it("returns Low for < 0.3", () => {
    expect(getTrustLabel(0.1)).toBe("Low");
  });

  it("returns Medium for 0.3-0.6", () => {
    expect(getTrustLabel(0.45)).toBe("Medium");
  });

  it("returns Good for 0.6-0.8", () => {
    expect(getTrustLabel(0.7)).toBe("Good");
  });

  it("returns High for >= 0.8", () => {
    expect(getTrustLabel(0.92)).toBe("High");
  });
});

describe("TrustBar", () => {
  it("renders the trust value text", () => {
    render(<TrustBar value={0.92} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.92");
  });

  it("sets fill width proportional to value", () => {
    render(<TrustBar value={0.75} />);
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.style.width).toBe("75%");
  });

  it("renders correct color for low trust", () => {
    render(<TrustBar value={0.2} />);
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.className).toContain("bg-red-400");
  });

  it("renders correct color for medium trust", () => {
    render(<TrustBar value={0.5} />);
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.className).toContain("bg-yellow-400");
  });

  it("renders correct color for good trust", () => {
    render(<TrustBar value={0.7} />);
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.className).toContain("bg-green-400");
  });

  it("renders correct color for high trust", () => {
    render(<TrustBar value={0.9} />);
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.className).toContain("bg-green-600");
  });

  it("has progressbar role with aria values", () => {
    render(<TrustBar value={0.85} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "85");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-label", "Trust: High");
  });

  it("clamps values above 1.0", () => {
    render(<TrustBar value={1.5} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("1.00");
    expect(screen.getByTestId("trust-bar-fill").style.width).toBe("100%");
  });

  it("clamps values below 0.0", () => {
    render(<TrustBar value={-0.5} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.00");
    expect(screen.getByTestId("trust-bar-fill").style.width).toBe("0%");
  });

  it("handles boundary value 0.0", () => {
    render(<TrustBar value={0} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.00");
    const fill = screen.getByTestId("trust-bar-fill");
    expect(fill.className).toContain("bg-red-400");
  });

  it("handles boundary value 1.0", () => {
    render(<TrustBar value={1.0} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("1.00");
    expect(screen.getByTestId("trust-bar-fill").style.width).toBe("100%");
  });

  it("renders exactly 0.30 boundary as yellow", () => {
    render(<TrustBar value={0.3} />);
    expect(screen.getByTestId("trust-bar-fill").className).toContain("bg-yellow-400");
  });

  it("renders exactly 0.60 boundary as green-400", () => {
    render(<TrustBar value={0.6} />);
    expect(screen.getByTestId("trust-bar-fill").className).toContain("bg-green-400");
  });

  it("renders exactly 0.80 boundary as green-600", () => {
    render(<TrustBar value={0.8} />);
    expect(screen.getByTestId("trust-bar-fill").className).toContain("bg-green-600");
  });
});
