import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import TopStoriesSection from "@/components/dashboard/TopStoriesSection";
import { makeTopStories } from "../helpers/fixtures";

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

describe("TopStoriesSection", () => {
  it("renders loading skeletons", () => {
    render(<TopStoriesSection stories={[]} isLoading={true} />);
    expect(screen.getByText("Top Stories")).toBeInTheDocument();
    expect(screen.getByTestId("stories-skeleton")).toBeInTheDocument();
    expect(
      screen.getByTestId("stories-skeleton").children,
    ).toHaveLength(5);
  });

  it("renders empty state when no stories", () => {
    render(<TopStoriesSection stories={[]} isLoading={false} />);
    expect(screen.getByTestId("stories-empty")).toHaveTextContent(
      "Stories are being analyzed",
    );
  });

  it("renders story cards when data is available", () => {
    const stories = makeTopStories(3);
    render(<TopStoriesSection stories={stories} isLoading={false} />);
    expect(screen.getAllByTestId("story-card")).toHaveLength(3);
  });

  it("renders all 5 top stories", () => {
    const stories = makeTopStories(5);
    render(<TopStoriesSection stories={stories} isLoading={false} />);
    expect(screen.getAllByTestId("story-card")).toHaveLength(5);
  });

  it("renders section heading", () => {
    render(<TopStoriesSection stories={makeTopStories()} isLoading={false} />);
    expect(screen.getByText("Top Stories")).toBeInTheDocument();
  });

  it("renders View all stories link", () => {
    render(<TopStoriesSection stories={makeTopStories()} isLoading={false} />);
    const link = screen.getByText(/View all stories/);
    expect(link).toHaveAttribute("href", "/stories");
  });

  it("does not render View all link when empty", () => {
    render(<TopStoriesSection stories={[]} isLoading={false} />);
    expect(screen.queryByText(/View all stories/)).toBeNull();
  });

  it("does not render View all link when loading", () => {
    render(<TopStoriesSection stories={[]} isLoading={true} />);
    expect(screen.queryByText(/View all stories/)).toBeNull();
  });
});
