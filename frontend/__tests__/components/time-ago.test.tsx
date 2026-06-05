import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TimeAgo, { formatTimeAgo } from "@/components/dashboard/TimeAgo";

describe("formatTimeAgo", () => {
  const now = new Date("2026-06-05T12:00:00Z").getTime();

  it("returns 'just now' for less than 1 minute ago", () => {
    const date = new Date(now - 30_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("just now");
  });

  it("returns minutes for under 1 hour", () => {
    const date = new Date(now - 15 * 60_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("15m ago");
  });

  it("returns 1m for exactly 1 minute", () => {
    const date = new Date(now - 60_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("1m ago");
  });

  it("returns 59m for 59 minutes", () => {
    const date = new Date(now - 59 * 60_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("59m ago");
  });

  it("returns hours for under 24 hours", () => {
    const date = new Date(now - 3 * 3_600_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("3h ago");
  });

  it("returns 1h for exactly 1 hour", () => {
    const date = new Date(now - 3_600_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("1h ago");
  });

  it("returns days for 24+ hours", () => {
    const date = new Date(now - 48 * 3_600_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("2d ago");
  });

  it("returns 1d for exactly 24 hours", () => {
    const date = new Date(now - 24 * 3_600_000).toISOString();
    expect(formatTimeAgo(date, now)).toBe("1d ago");
  });
});

describe("TimeAgo component", () => {
  it("renders a time element", () => {
    const date = new Date().toISOString();
    render(<TimeAgo date={date} />);
    const el = screen.getByText(/ago|just now/);
    expect(el.tagName).toBe("TIME");
  });

  it("has dateTime attribute", () => {
    const date = new Date().toISOString();
    render(<TimeAgo date={date} />);
    const el = screen.getByText(/ago|just now/);
    expect(el).toHaveAttribute("dateTime", date);
  });

  it("has title with localized date string", () => {
    const date = "2026-06-05T12:00:00Z";
    render(<TimeAgo date={date} />);
    const el = screen.getByText(/ago|just now/);
    expect(el).toHaveAttribute("title");
    expect(el.getAttribute("title")).toBeTruthy();
  });
});
