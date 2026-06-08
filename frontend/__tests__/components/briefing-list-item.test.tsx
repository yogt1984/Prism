import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BriefingListItem, {
  formatDate,
} from "@/components/briefing/BriefingListItem";
import { makeBriefing } from "../helpers/fixtures";

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

describe("BriefingListItem", () => {
  it("renders as a link to briefing detail", () => {
    const briefing = makeBriefing({ id: 42 });
    render(<BriefingListItem briefing={briefing} />);
    const link = screen.getByTestId("briefing-list-item");
    expect(link).toHaveAttribute("href", "/briefings/42");
  });

  it("renders date column", () => {
    const briefing = makeBriefing();
    render(<BriefingListItem briefing={briefing} />);
    expect(screen.getByTestId("date-column")).toBeInTheDocument();
  });

  it("renders story count badge", () => {
    const briefing = makeBriefing({ story_count: 8 });
    render(<BriefingListItem briefing={briefing} />);
    expect(screen.getByTestId("story-count-badge")).toHaveTextContent(
      "8 stories",
    );
  });

  it("renders sent badge", () => {
    const briefing = makeBriefing({ sent: true });
    render(<BriefingListItem briefing={briefing} />);
    expect(screen.getByTestId("sent-badge")).toHaveTextContent("Sent");
  });

  it("renders draft badge for unsent", () => {
    const briefing = makeBriefing({ sent: false });
    render(<BriefingListItem briefing={briefing} />);
    expect(screen.getByTestId("sent-badge")).toHaveTextContent("Draft");
  });

  it("renders prompt version tag", () => {
    const briefing = makeBriefing({ prompt_version: "v3" });
    render(<BriefingListItem briefing={briefing} />);
    expect(screen.getByTestId("prompt-version-tag")).toHaveTextContent("v3");
  });

  it("renders chevron icon", () => {
    const briefing = makeBriefing();
    const { container } = render(<BriefingListItem briefing={briefing} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});

describe("formatDate", () => {
  it("returns day, date, and time strings", () => {
    const result = formatDate("2026-06-05T07:00:00Z");
    expect(result.day).toBeTruthy();
    expect(result.date).toBeTruthy();
    expect(result.time).toBeTruthy();
  });

  it("produces consistent output for a known date", () => {
    const result = formatDate("2026-01-01T12:00:00Z");
    expect(result.date).toContain("2026");
    expect(result.date).toContain("Jan");
  });
});
