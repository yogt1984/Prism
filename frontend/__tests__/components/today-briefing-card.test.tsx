import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TodayBriefingCard from "@/components/dashboard/TodayBriefingCard";
import { makeBriefing, makeBriefingDetail } from "../helpers/fixtures";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

describe("TodayBriefingCard", () => {
  it("renders loading skeleton", () => {
    render(
      <TodayBriefingCard isLoading={true} />,
    );
    expect(screen.getByTestId("briefing-skeleton")).toBeInTheDocument();
  });

  it("renders empty state when no briefing", () => {
    render(
      <TodayBriefingCard isLoading={false} briefing={null} />,
    );
    expect(screen.getByTestId("briefing-empty")).toBeInTheDocument();
    expect(
      screen.getByText(/No briefing yet/),
    ).toBeInTheDocument();
  });

  it("shows Generate now button in empty state", () => {
    const onTrigger = vi.fn();
    render(
      <TodayBriefingCard
        isLoading={false}
        briefing={null}
        onTrigger={onTrigger}
      />,
    );
    expect(screen.getByText("Generate now")).toBeInTheDocument();
  });

  it("calls onTrigger when Generate now is clicked", async () => {
    const user = userEvent.setup();
    const onTrigger = vi.fn();
    render(
      <TodayBriefingCard
        isLoading={false}
        briefing={null}
        onTrigger={onTrigger}
      />,
    );
    await user.click(screen.getByText("Generate now"));
    expect(onTrigger).toHaveBeenCalledOnce();
  });

  it("shows Generating... when trigger is pending", () => {
    render(
      <TodayBriefingCard
        isLoading={false}
        briefing={null}
        onTrigger={() => {}}
        isTriggerPending={true}
      />,
    );
    expect(screen.getByText("Generating...")).toBeDisabled();
  });

  it("does not show generate button when onTrigger not provided", () => {
    render(
      <TodayBriefingCard isLoading={false} briefing={null} />,
    );
    expect(screen.queryByText("Generate now")).toBeNull();
  });

  it("renders briefing with title and date", () => {
    const briefing = makeBriefing({ created_at: "2026-06-05T06:58:12Z" });
    render(
      <TodayBriefingCard isLoading={false} briefing={briefing} />,
    );
    expect(screen.getByText("Today's Briefing")).toBeInTheDocument();
  });

  it("renders story count", () => {
    const briefing = makeBriefing({ story_count: 10 });
    render(
      <TodayBriefingCard isLoading={false} briefing={briefing} />,
    );
    expect(screen.getByText("10 stories")).toBeInTheDocument();
  });

  it("renders View full briefing link", () => {
    const briefing = makeBriefing({ id: 42 });
    render(
      <TodayBriefingCard isLoading={false} briefing={briefing} />,
    );
    const link = screen.getByText(/View full briefing/);
    expect(link).toHaveAttribute("href", "/briefings/42");
  });

  it("renders HTML preview stripped of tags and truncated", () => {
    const briefing = makeBriefing();
    const detail = makeBriefingDetail({
      content_html: "<h2>Title</h2><p>Some long content here.</p>",
    });
    render(
      <TodayBriefingCard
        isLoading={false}
        briefing={briefing}
        detail={detail}
      />,
    );
    expect(screen.getByText(/TitleSome long content here/)).toBeInTheDocument();
  });

  it("truncates preview to 300 characters", () => {
    const briefing = makeBriefing();
    const longText = "A".repeat(500);
    const detail = makeBriefingDetail({
      content_html: `<p>${longText}</p>`,
    });
    render(
      <TodayBriefingCard
        isLoading={false}
        briefing={briefing}
        detail={detail}
      />,
    );
    const preview = screen.getByText(/^A+$/);
    expect(preview.textContent!.length).toBe(300);
  });

  it("renders without detail (no preview text)", () => {
    const briefing = makeBriefing();
    render(
      <TodayBriefingCard isLoading={false} briefing={briefing} />,
    );
    expect(screen.getByText("Today's Briefing")).toBeInTheDocument();
    expect(screen.getByText(/stories/)).toBeInTheDocument();
  });
});
