import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SentimentBar, {
  getMarkerColor,
} from "@/components/story/SentimentBar";

describe("SentimentBar", () => {
  it("renders the bar container", () => {
    render(<SentimentBar value={0} />);
    expect(screen.getByTestId("sentiment-bar")).toBeInTheDocument();
  });

  it("renders the marker", () => {
    render(<SentimentBar value={0} />);
    expect(screen.getByTestId("sentiment-marker")).toBeInTheDocument();
  });

  it("positions marker at 50% for neutral (0)", () => {
    render(<SentimentBar value={0} />);
    const marker = screen.getByTestId("sentiment-marker");
    expect(marker.style.left).toBe("50%");
  });

  it("positions marker at 0% for value -1", () => {
    render(<SentimentBar value={-1} />);
    const marker = screen.getByTestId("sentiment-marker");
    expect(marker.style.left).toBe("0%");
  });

  it("positions marker at 100% for value 1", () => {
    render(<SentimentBar value={1} />);
    const marker = screen.getByTestId("sentiment-marker");
    expect(marker.style.left).toBe("100%");
  });

  it("positions marker at 25% for value -0.5", () => {
    render(<SentimentBar value={-0.5} />);
    const marker = screen.getByTestId("sentiment-marker");
    expect(marker.style.left).toBe("25%");
  });

  it("positions marker at 75% for value 0.5", () => {
    render(<SentimentBar value={0.5} />);
    const marker = screen.getByTestId("sentiment-marker");
    expect(marker.style.left).toBe("75%");
  });

  it("includes aria-label with sentiment value", () => {
    render(<SentimentBar value={0.42} />);
    expect(screen.getByTestId("sentiment-bar")).toHaveAttribute(
      "aria-label",
      "Sentiment: 0.42",
    );
  });

  it("shows center line", () => {
    const { container } = render(<SentimentBar value={0} />);
    const centerLine = container.querySelector(".bg-gray-300");
    expect(centerLine).toBeInTheDocument();
  });
});

describe("getMarkerColor", () => {
  it("returns red for strongly negative (-0.5)", () => {
    expect(getMarkerColor(-0.5)).toBe("bg-red-500");
  });

  it("returns red for -0.31", () => {
    expect(getMarkerColor(-0.31)).toBe("bg-red-500");
  });

  it("returns orange for moderately negative (-0.2)", () => {
    expect(getMarkerColor(-0.2)).toBe("bg-orange-400");
  });

  it("returns orange for -0.11", () => {
    expect(getMarkerColor(-0.11)).toBe("bg-orange-400");
  });

  it("returns gray for neutral (0)", () => {
    expect(getMarkerColor(0)).toBe("bg-gray-400");
  });

  it("returns gray for -0.1", () => {
    expect(getMarkerColor(-0.1)).toBe("bg-gray-400");
  });

  it("returns gray for 0.1", () => {
    expect(getMarkerColor(0.1)).toBe("bg-gray-400");
  });

  it("returns lime for moderately positive (0.2)", () => {
    expect(getMarkerColor(0.2)).toBe("bg-lime-400");
  });

  it("returns lime for 0.3", () => {
    expect(getMarkerColor(0.3)).toBe("bg-lime-400");
  });

  it("returns green for strongly positive (0.5)", () => {
    expect(getMarkerColor(0.5)).toBe("bg-green-500");
  });

  it("returns green for 0.31", () => {
    expect(getMarkerColor(0.31)).toBe("bg-green-500");
  });

  it("returns green for max positive (1.0)", () => {
    expect(getMarkerColor(1.0)).toBe("bg-green-500");
  });

  it("returns red for max negative (-1.0)", () => {
    expect(getMarkerColor(-1.0)).toBe("bg-red-500");
  });
});
