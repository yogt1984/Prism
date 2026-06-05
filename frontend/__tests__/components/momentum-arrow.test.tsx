import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MomentumArrow from "@/components/dashboard/MomentumArrow";

describe("MomentumArrow", () => {
  it("shows rising arrow for positive momentum", () => {
    render(<MomentumArrow momentum={0.5} />);
    expect(screen.getByLabelText("rising")).toHaveTextContent("\u25B2");
  });

  it("shows falling arrow for negative momentum", () => {
    render(<MomentumArrow momentum={-0.3} />);
    expect(screen.getByLabelText("falling")).toHaveTextContent("\u25BC");
  });

  it("shows flat indicator for near-zero momentum", () => {
    render(<MomentumArrow momentum={0.05} />);
    expect(screen.getByLabelText("flat")).toHaveTextContent("\u2500");
  });

  it("shows flat for exactly zero", () => {
    render(<MomentumArrow momentum={0} />);
    expect(screen.getByLabelText("flat")).toBeInTheDocument();
  });

  it("shows flat for negative near-zero", () => {
    render(<MomentumArrow momentum={-0.09} />);
    expect(screen.getByLabelText("flat")).toBeInTheDocument();
  });

  it("uses green color for rising", () => {
    render(<MomentumArrow momentum={0.2} />);
    expect(screen.getByLabelText("rising").className).toContain("green");
  });

  it("uses red color for falling", () => {
    render(<MomentumArrow momentum={-0.2} />);
    expect(screen.getByLabelText("falling").className).toContain("red");
  });

  it("uses gray color for flat", () => {
    render(<MomentumArrow momentum={0} />);
    expect(screen.getByLabelText("flat").className).toContain("gray");
  });

  it("treats threshold 0.1 as rising", () => {
    render(<MomentumArrow momentum={0.1} />);
    expect(screen.getByLabelText("rising")).toBeInTheDocument();
  });

  it("treats threshold -0.1 as falling", () => {
    render(<MomentumArrow momentum={-0.1} />);
    expect(screen.getByLabelText("falling")).toBeInTheDocument();
  });
});
