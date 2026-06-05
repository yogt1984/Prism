import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Sparkline from "@/components/dashboard/Sparkline";

function makeData(perceptions: number[]) {
  return perceptions.map((p, i) => ({
    perception: p,
    computed_at: new Date(Date.now() - (perceptions.length - i) * 3600000).toISOString(),
  }));
}

describe("Sparkline", () => {
  it("renders nothing with empty data", () => {
    const { container } = render(<Sparkline data={[]} />);
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders an SVG with default dimensions", () => {
    render(<Sparkline data={makeData([0, 0.5, -0.5])} />);
    const svg = screen.getByRole("img", { name: "Perception sparkline" });
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("width", "80");
    expect(svg).toHaveAttribute("height", "24");
  });

  it("renders with custom dimensions", () => {
    render(<Sparkline data={makeData([0, 0.5])} width={120} height={40} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("width", "120");
    expect(svg).toHaveAttribute("height", "40");
  });

  it("renders a polyline element", () => {
    const { container } = render(<Sparkline data={makeData([0, 0.5, -0.5])} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeInTheDocument();
    expect(polyline).toHaveAttribute("points");
    expect(polyline!.getAttribute("fill")).toBe("none");
  });

  it("generates correct number of points", () => {
    const data = makeData([0, 0.2, 0.4, -0.1, 0.3]);
    const { container } = render(<Sparkline data={data} />);
    const polyline = container.querySelector("polyline");
    const points = polyline!.getAttribute("points")!.trim().split(" ");
    expect(points).toHaveLength(5);
  });

  it("uses green stroke for positive momentum", () => {
    const { container } = render(
      <Sparkline data={makeData([0, 0.5])} momentum={0.5} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toHaveAttribute("stroke", "#22c55e");
  });

  it("uses red stroke for negative momentum", () => {
    const { container } = render(
      <Sparkline data={makeData([0, -0.5])} momentum={-0.3} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toHaveAttribute("stroke", "#ef4444");
  });

  it("uses gray stroke for flat momentum", () => {
    const { container } = render(
      <Sparkline data={makeData([0, 0.1])} momentum={0.05} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toHaveAttribute("stroke", "#9ca3af");
  });

  it("uses gray stroke when momentum is zero", () => {
    const { container } = render(
      <Sparkline data={makeData([0, 0.1])} momentum={0} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toHaveAttribute("stroke", "#9ca3af");
  });

  it("maps perception -1 to bottom of chart and +1 to top", () => {
    const { container } = render(
      <Sparkline data={makeData([-1, 1])} width={80} height={24} />,
    );
    const polyline = container.querySelector("polyline");
    const points = polyline!.getAttribute("points")!.trim().split(" ");
    // perception -1 → y = 24 (bottom), perception 1 → y = 0 (top)
    const [p1, p2] = points.map((p) => p.split(",").map(Number));
    expect(p1[1]).toBeCloseTo(24, 0); // bottom
    expect(p2[1]).toBeCloseTo(0, 0); // top
  });

  it("handles single data point", () => {
    const { container } = render(
      <Sparkline data={makeData([0.5])} width={80} height={24} />,
    );
    const polyline = container.querySelector("polyline");
    const points = polyline!.getAttribute("points")!.trim().split(" ");
    expect(points).toHaveLength(1);
    // Single point should be centered at x = width/2
    const x = parseFloat(points[0].split(",")[0]);
    expect(x).toBeCloseTo(40, 0);
  });

  it("has accessible role and label", () => {
    render(<Sparkline data={makeData([0, 0.5])} />);
    expect(
      screen.getByRole("img", { name: "Perception sparkline" }),
    ).toBeInTheDocument();
  });
});
