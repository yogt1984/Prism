import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import StoryRow, {
  CATEGORY_DOT_COLORS,
} from "@/components/dashboard/StoryRow";
import { makeStory } from "../helpers/fixtures";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("StoryRow", () => {
  it("renders headline", () => {
    const story = makeStory({ headline: "Breaking: Economy Update" });
    render(<StoryRow story={story} />);
    expect(screen.getByText("Breaking: Economy Update")).toBeInTheDocument();
  });

  it("links to story detail page", () => {
    const story = makeStory({ id: 456 });
    render(<StoryRow story={story} />);
    expect(screen.getByTestId("story-row")).toHaveAttribute(
      "href",
      "/stories/456",
    );
  });

  it("renders resonance score with one decimal", () => {
    const story = makeStory({ resonance_score: 3.14 });
    render(<StoryRow story={story} />);
    expect(screen.getByText("3.1")).toBeInTheDocument();
  });

  it("renders time ago", () => {
    const story = makeStory({
      first_seen: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    });
    render(<StoryRow story={story} />);
    expect(screen.getByText("2h ago")).toBeInTheDocument();
  });

  it("renders category dot for finance", () => {
    const story = makeStory({ categories: "finance" });
    render(<StoryRow story={story} />);
    const dot = screen.getByTestId("category-dot");
    expect(dot.className).toContain("emerald");
  });

  it("renders category dot for politics", () => {
    const story = makeStory({ categories: "politics,finance" });
    render(<StoryRow story={story} />);
    const dot = screen.getByTestId("category-dot");
    expect(dot.className).toContain("red");
  });

  it("uses gray dot for unknown category", () => {
    const story = makeStory({ categories: "unknown" });
    render(<StoryRow story={story} />);
    const dot = screen.getByTestId("category-dot");
    expect(dot.className).toContain("gray");
  });

  it("uses first category for dot color when multiple", () => {
    const story = makeStory({ categories: "technology,finance" });
    render(<StoryRow story={story} />);
    const dot = screen.getByTestId("category-dot");
    expect(dot.className).toContain("blue");
  });

  it("has all 8 categories in CATEGORY_DOT_COLORS", () => {
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
    expect(Object.keys(CATEGORY_DOT_COLORS).sort()).toEqual(expected.sort());
  });

  it("dot is a small circle", () => {
    const story = makeStory();
    render(<StoryRow story={story} />);
    const dot = screen.getByTestId("category-dot");
    expect(dot.className).toContain("rounded-full");
    expect(dot.className).toContain("w-2");
    expect(dot.className).toContain("h-2");
  });
});
