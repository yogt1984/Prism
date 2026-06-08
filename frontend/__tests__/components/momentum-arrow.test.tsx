import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MomentumArrow, {
  getMomentumDirection,
  getMomentumColor,
} from "@/components/perception/MomentumArrow";

describe("getMomentumDirection", () => {
  it("returns rising for positive momentum", () => {
    expect(getMomentumDirection(0.15)).toBe("rising");
    expect(getMomentumDirection(0.02)).toBe("rising");
  });

  it("returns falling for negative momentum", () => {
    expect(getMomentumDirection(-0.15)).toBe("falling");
    expect(getMomentumDirection(-0.02)).toBe("falling");
  });

  it("returns stable for near-zero momentum", () => {
    expect(getMomentumDirection(0)).toBe("stable");
    expect(getMomentumDirection(0.005)).toBe("stable");
    expect(getMomentumDirection(-0.005)).toBe("stable");
    expect(getMomentumDirection(0.01)).toBe("stable");
    expect(getMomentumDirection(-0.01)).toBe("stable");
  });

  it("boundary: 0.01 is stable, 0.011 is rising", () => {
    expect(getMomentumDirection(0.01)).toBe("stable");
    expect(getMomentumDirection(0.011)).toBe("rising");
  });

  it("boundary: -0.01 is stable, -0.011 is falling", () => {
    expect(getMomentumDirection(-0.01)).toBe("stable");
    expect(getMomentumDirection(-0.011)).toBe("falling");
  });
});

describe("getMomentumColor", () => {
  it("returns green for rising", () => {
    expect(getMomentumColor("rising")).toBe("text-green-600");
  });

  it("returns red for falling", () => {
    expect(getMomentumColor("falling")).toBe("text-red-500");
  });

  it("returns gray for stable", () => {
    expect(getMomentumColor("stable")).toBe("text-gray-400");
  });
});

describe("MomentumArrow", () => {
  it("renders up arrow for positive momentum", () => {
    render(<MomentumArrow value={0.15} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveTextContent("\u2191");
    expect(el.className).toContain("text-green-600");
  });

  it("renders down arrow for negative momentum", () => {
    render(<MomentumArrow value={-0.12} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveTextContent("\u2193");
    expect(el.className).toContain("text-red-500");
  });

  it("renders right arrow for stable momentum", () => {
    render(<MomentumArrow value={0.005} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveTextContent("\u2192");
    expect(el.className).toContain("text-gray-400");
  });

  it("shows momentum value in title", () => {
    render(<MomentumArrow value={0.15} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveAttribute("title", "Momentum: +0.15");
  });

  it("shows negative value in title", () => {
    render(<MomentumArrow value={-0.05} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveAttribute("title", "Momentum: -0.05");
  });

  it("shows zero value in title with + prefix", () => {
    render(<MomentumArrow value={0} />);
    const el = screen.getByTestId("momentum-arrow");
    expect(el).toHaveAttribute("title", "Momentum: +0.00");
  });
});
