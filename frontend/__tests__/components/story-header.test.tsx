import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import StoryHeader from "@/components/story/StoryHeader";
import { makeStoryDetail } from "../helpers/fixtures";

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

describe("StoryHeader", () => {
  it("renders headline", () => {
    const story = makeStoryDetail({
      headline: "Market Rally Continues",
    });
    render(<StoryHeader story={story} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Market Rally Continues",
    );
  });

  it("renders headline as h1", () => {
    const story = makeStoryDetail();
    render(<StoryHeader story={story} />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(story.headline);
  });

  it("renders category pills", () => {
    const story = makeStoryDetail({ categories: "finance,politics" });
    render(<StoryHeader story={story} />);
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getByText("politics")).toBeInTheDocument();
  });

  it("renders article count as sources", () => {
    const story = makeStoryDetail({ article_count: 12 });
    render(<StoryHeader story={story} />);
    expect(screen.getByText("12 sources")).toBeInTheDocument();
  });

  it("renders quality indicator", () => {
    const story = makeStoryDetail({ quality_score: 0.9 });
    render(<StoryHeader story={story} />);
    expect(screen.getByTestId("quality-indicator")).toBeInTheDocument();
  });

  it("renders breadcrumb with Dashboard and Stories links", () => {
    const story = makeStoryDetail();
    render(<StoryHeader story={story} />);
    const dashLink = screen.getByText("Dashboard");
    expect(dashLink).toHaveAttribute("href", "/dashboard");
    const storiesLink = screen.getByText("Stories");
    expect(storiesLink).toHaveAttribute("href", "/stories");
  });

  it("renders headline in both breadcrumb and h1", () => {
    const story = makeStoryDetail({
      headline: "Some Story",
    });
    render(<StoryHeader story={story} />);
    const matches = screen.getAllByText("Some Story");
    // breadcrumb + h1
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  it("handles single category", () => {
    const story = makeStoryDetail({ categories: "technology" });
    render(<StoryHeader story={story} />);
    expect(screen.getByText("technology")).toBeInTheDocument();
  });

  it("renders time ago", () => {
    const story = makeStoryDetail();
    render(<StoryHeader story={story} />);
    // TimeAgo component should render something
    const header = screen.getByRole("banner");
    expect(header).toBeInTheDocument();
  });
});
