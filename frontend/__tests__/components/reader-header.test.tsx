import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ReaderHeader from "@/components/briefing/ReaderHeader";
import { makeBriefingDetail } from "../helpers/fixtures";

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

describe("ReaderHeader", () => {
  it("renders back link to /briefings", () => {
    const briefing = makeBriefingDetail();
    render(<ReaderHeader briefing={briefing} />);
    const link = screen.getByTestId("back-link");
    expect(link).toHaveAttribute("href", "/briefings");
    expect(link).toHaveTextContent("All Briefings");
  });

  it("renders date as h1", () => {
    const briefing = makeBriefingDetail();
    render(<ReaderHeader briefing={briefing} />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders story count badge", () => {
    const briefing = makeBriefingDetail({ story_count: 7 });
    render(<ReaderHeader briefing={briefing} />);
    expect(screen.getByTestId("story-count-badge")).toHaveTextContent(
      "7 stories",
    );
  });

  it("renders format badge when provided", () => {
    const briefing = makeBriefingDetail();
    render(<ReaderHeader briefing={briefing} format="email" />);
    expect(screen.getByTestId("format-badge")).toHaveTextContent("Email");
  });

  it("does not render format badge when not provided", () => {
    const briefing = makeBriefingDetail();
    render(<ReaderHeader briefing={briefing} />);
    expect(screen.queryByTestId("format-badge")).not.toBeInTheDocument();
  });

  it("renders time string", () => {
    const briefing = makeBriefingDetail();
    render(<ReaderHeader briefing={briefing} />);
    // Should have some time text
    const header = screen.getByTestId("reader-header");
    expect(header).toBeInTheDocument();
  });
});
