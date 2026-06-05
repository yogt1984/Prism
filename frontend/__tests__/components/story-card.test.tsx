import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import StoryCard from "@/components/dashboard/StoryCard";
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

describe("StoryCard", () => {
  it("renders headline", () => {
    const story = makeStory({ headline: "Big News Today" });
    render(<StoryCard story={story} />);
    expect(screen.getByText("Big News Today")).toBeInTheDocument();
  });

  it("links to story detail page", () => {
    const story = makeStory({ id: 123 });
    render(<StoryCard story={story} />);
    expect(screen.getByTestId("story-card")).toHaveAttribute(
      "href",
      "/stories/123",
    );
  });

  it("renders category pills", () => {
    const story = makeStory({ categories: "finance,politics" });
    render(<StoryCard story={story} />);
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getByText("politics")).toBeInTheDocument();
  });

  it("renders single category", () => {
    const story = makeStory({ categories: "technology" });
    render(<StoryCard story={story} />);
    expect(screen.getByText("technology")).toBeInTheDocument();
  });

  it("renders resonance badge", () => {
    const story = makeStory({ resonance_score: 4.72 });
    render(<StoryCard story={story} />);
    expect(screen.getByTestId("resonance-badge")).toHaveTextContent("4.7");
  });

  it("renders source count", () => {
    const story = makeStory({ article_count: 8 });
    render(<StoryCard story={story} />);
    expect(screen.getByText("8 sources")).toBeInTheDocument();
  });

  it("renders time ago", () => {
    const story = makeStory({
      first_seen: new Date(Date.now() - 3_600_000).toISOString(),
    });
    render(<StoryCard story={story} />);
    expect(screen.getByText("1h ago")).toBeInTheDocument();
  });

  it("handles empty categories gracefully", () => {
    const story = makeStory({ categories: "" });
    render(<StoryCard story={story} />);
    expect(screen.getByText(story.headline)).toBeInTheDocument();
  });

  it("has minimum width for horizontal scrolling", () => {
    const story = makeStory();
    render(<StoryCard story={story} />);
    expect(screen.getByTestId("story-card").className).toContain(
      "min-w-[240px]",
    );
  });
});
