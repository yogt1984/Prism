import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StoryCountBadge from "@/components/briefing/StoryCountBadge";

describe("StoryCountBadge", () => {
  it('shows "1 story" for count 1', () => {
    render(<StoryCountBadge count={1} />);
    expect(screen.getByTestId("story-count-badge")).toHaveTextContent(
      "1 story",
    );
  });

  it('shows "5 stories" for count 5', () => {
    render(<StoryCountBadge count={5} />);
    expect(screen.getByTestId("story-count-badge")).toHaveTextContent(
      "5 stories",
    );
  });

  it('shows "0 stories" for count 0', () => {
    render(<StoryCountBadge count={0} />);
    expect(screen.getByTestId("story-count-badge")).toHaveTextContent(
      "0 stories",
    );
  });

  it("renders with violet styling", () => {
    render(<StoryCountBadge count={3} />);
    const el = screen.getByTestId("story-count-badge");
    expect(el.className).toContain("bg-violet-100");
    expect(el.className).toContain("text-violet-700");
  });
});
