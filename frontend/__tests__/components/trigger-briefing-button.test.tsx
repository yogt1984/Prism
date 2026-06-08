import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import TriggerBriefingButton, {
  RATE_GUARD_MS,
  STORAGE_KEY,
} from "@/components/briefing/TriggerBriefingButton";

describe("TriggerBriefingButton", () => {
  let onTrigger: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onTrigger = vi.fn();
    vi.useFakeTimers();
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders button text", () => {
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    expect(screen.getByTestId("trigger-briefing-btn")).toHaveTextContent(
      "Generate new briefing",
    );
  });

  it("calls onTrigger on click", () => {
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    fireEvent.click(screen.getByTestId("trigger-briefing-btn"));
    expect(onTrigger).toHaveBeenCalledTimes(1);
  });

  it('shows "Generating..." when isPending', () => {
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={true} />,
    );
    expect(screen.getByTestId("trigger-briefing-btn")).toHaveTextContent(
      "Generating...",
    );
  });

  it("shows spinner when isPending", () => {
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={true} />,
    );
    expect(screen.getByTestId("trigger-spinner")).toBeInTheDocument();
  });

  it("is disabled when isPending", () => {
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={true} />,
    );
    expect(screen.getByTestId("trigger-briefing-btn")).toBeDisabled();
  });

  it("enters cooldown after click (rate guard)", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    fireEvent.click(screen.getByTestId("trigger-briefing-btn"));
    expect(screen.getByTestId("trigger-briefing-btn")).toBeDisabled();
  });

  it("stores timestamp in localStorage on click", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    fireEvent.click(screen.getByTestId("trigger-briefing-btn"));
    expect(localStorage.getItem(STORAGE_KEY)).toBeTruthy();
  });

  it("re-enables after cooldown period", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    fireEvent.click(screen.getByTestId("trigger-briefing-btn"));
    expect(screen.getByTestId("trigger-briefing-btn")).toBeDisabled();

    act(() => {
      vi.advanceTimersByTime(RATE_GUARD_MS);
    });
    expect(screen.getByTestId("trigger-briefing-btn")).not.toBeDisabled();
  });

  it("starts in cooldown if localStorage has recent timestamp", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:30Z"));
    localStorage.setItem(
      STORAGE_KEY,
      String(new Date("2026-01-01T00:00:00Z").getTime()),
    );

    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    expect(screen.getByTestId("trigger-briefing-btn")).toBeDisabled();
  });

  it("not in cooldown if localStorage timestamp is old", () => {
    vi.setSystemTime(new Date("2026-01-01T00:02:00Z"));
    localStorage.setItem(
      STORAGE_KEY,
      String(new Date("2026-01-01T00:00:00Z").getTime()),
    );

    render(
      <TriggerBriefingButton onTrigger={onTrigger} isPending={false} />,
    );
    expect(screen.getByTestId("trigger-briefing-btn")).not.toBeDisabled();
  });

  it("RATE_GUARD_MS is 60 seconds", () => {
    expect(RATE_GUARD_MS).toBe(60_000);
  });
});
