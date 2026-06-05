import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import CategoryPill, {
  CATEGORY_COLORS,
} from "@/components/dashboard/CategoryPill";

describe("CategoryPill", () => {
  it("renders the category name capitalized", () => {
    render(<CategoryPill category="finance" />);
    expect(screen.getByText("finance")).toBeInTheDocument();
    // CSS capitalize class handles visual capitalization
    expect(screen.getByText("finance").className).toContain("capitalize");
  });

  it("applies emerald colors for finance", () => {
    render(<CategoryPill category="finance" />);
    const pill = screen.getByText("finance");
    expect(pill.className).toContain("emerald");
  });

  it("applies red colors for politics", () => {
    render(<CategoryPill category="politics" />);
    expect(screen.getByText("politics").className).toContain("red");
  });

  it("applies blue colors for technology", () => {
    render(<CategoryPill category="technology" />);
    expect(screen.getByText("technology").className).toContain("blue");
  });

  it("applies orange colors for sports", () => {
    render(<CategoryPill category="sports" />);
    expect(screen.getByText("sports").className).toContain("orange");
  });

  it("applies purple colors for culture", () => {
    render(<CategoryPill category="culture" />);
    expect(screen.getByText("culture").className).toContain("purple");
  });

  it("applies cyan colors for science", () => {
    render(<CategoryPill category="science" />);
    expect(screen.getByText("science").className).toContain("cyan");
  });

  it("applies pink colors for health", () => {
    render(<CategoryPill category="health" />);
    expect(screen.getByText("health").className).toContain("pink");
  });

  it("applies amber colors for world", () => {
    render(<CategoryPill category="world" />);
    expect(screen.getByText("world").className).toContain("amber");
  });

  it("applies gray fallback for unknown category", () => {
    render(<CategoryPill category="unknown" />);
    expect(screen.getByText("unknown").className).toContain("gray");
  });

  it("renders as a span element", () => {
    render(<CategoryPill category="finance" />);
    expect(screen.getByText("finance").tagName).toBe("SPAN");
  });

  it("has rounded-full class for pill shape", () => {
    render(<CategoryPill category="finance" />);
    expect(screen.getByText("finance").className).toContain("rounded-full");
  });

  it("has all 8 categories defined in CATEGORY_COLORS", () => {
    const expected = [
      "finance",
      "politics",
      "technology",
      "sports",
      "culture",
      "science",
      "health",
      "world",
    ];
    expect(Object.keys(CATEGORY_COLORS).sort()).toEqual(expected.sort());
  });
});
