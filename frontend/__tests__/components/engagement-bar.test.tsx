import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import EngagementBar from "@/components/story/EngagementBar";

describe("EngagementBar", () => {
  let onEngage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onEngage = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the engagement bar", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    expect(screen.getByTestId("engagement-bar")).toBeInTheDocument();
  });

  it("renders Save, Skip, and Share buttons", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    expect(screen.getByTestId("save-btn")).toHaveTextContent("Save");
    expect(screen.getByTestId("skip-btn")).toHaveTextContent("Skip");
    expect(screen.getByTestId("share-btn")).toHaveTextContent("Share");
  });

  it('calls onEngage with "save" and read time on Save click', () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    vi.setSystemTime(new Date("2026-01-01T00:00:05Z")); // 5 seconds later
    fireEvent.click(screen.getByTestId("save-btn"));
    expect(onEngage).toHaveBeenCalledWith("save", 5);
  });

  it('calls onEngage with "skip" and read time on Skip click', () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    vi.setSystemTime(new Date("2026-01-01T00:00:10Z")); // 10 seconds later
    fireEvent.click(screen.getByTestId("skip-btn"));
    expect(onEngage).toHaveBeenCalledWith("skip", 10);
  });

  it('changes Save text to "Saved" after save action', () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    fireEvent.click(screen.getByTestId("save-btn"));
    expect(screen.getByTestId("save-btn")).toHaveTextContent("Saved");
  });

  it('changes Skip text to "Skipped" after skip action', () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    fireEvent.click(screen.getByTestId("skip-btn"));
    expect(screen.getByTestId("skip-btn")).toHaveTextContent("Skipped");
  });

  it("disables both action buttons after engagement", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    fireEvent.click(screen.getByTestId("save-btn"));
    expect(screen.getByTestId("save-btn")).toBeDisabled();
    expect(screen.getByTestId("skip-btn")).toBeDisabled();
  });

  it("disables action buttons when isPending", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={true}
        storyUrl="/stories/1"
      />,
    );
    expect(screen.getByTestId("save-btn")).toBeDisabled();
    expect(screen.getByTestId("skip-btn")).toBeDisabled();
  });

  it("Share button is always enabled", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={true}
        storyUrl="/stories/1"
      />,
    );
    expect(screen.getByTestId("share-btn")).not.toBeDisabled();
  });

  it("calls onEngage only once (second click is no-op)", () => {
    render(
      <EngagementBar
        onEngage={onEngage}
        isPending={false}
        storyUrl="/stories/1"
      />,
    );
    fireEvent.click(screen.getByTestId("save-btn"));
    fireEvent.click(screen.getByTestId("save-btn")); // second click (disabled)
    expect(onEngage).toHaveBeenCalledTimes(1);
  });

  describe("Share button", () => {
    it("copies story URL to clipboard", async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(
        <EngagementBar
          onEngage={onEngage}
          isPending={false}
          storyUrl="/stories/1"
        />,
      );
      await act(async () => {
        fireEvent.click(screen.getByTestId("share-btn"));
      });
      expect(writeText).toHaveBeenCalledWith(
        `${window.location.origin}/stories/1`,
      );
    });

    it('shows "Copied!" after successful clipboard write', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(
        <EngagementBar
          onEngage={onEngage}
          isPending={false}
          storyUrl="/stories/1"
        />,
      );
      await act(async () => {
        fireEvent.click(screen.getByTestId("share-btn"));
      });
      expect(screen.getByTestId("share-btn")).toHaveTextContent("Copied!");
    });

    it('reverts to "Share" after 2 seconds', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(
        <EngagementBar
          onEngage={onEngage}
          isPending={false}
          storyUrl="/stories/1"
        />,
      );
      await act(async () => {
        fireEvent.click(screen.getByTestId("share-btn"));
      });
      expect(screen.getByTestId("share-btn")).toHaveTextContent("Copied!");

      act(() => {
        vi.advanceTimersByTime(2000);
      });
      expect(screen.getByTestId("share-btn")).toHaveTextContent("Share");
    });

    it("handles clipboard failure silently", async () => {
      const writeText = vi.fn().mockRejectedValue(new Error("denied"));
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(
        <EngagementBar
          onEngage={onEngage}
          isPending={false}
          storyUrl="/stories/1"
        />,
      );
      await act(async () => {
        fireEvent.click(screen.getByTestId("share-btn"));
      });
      // Should not crash, remains "Share"
      expect(screen.getByTestId("share-btn")).toHaveTextContent("Share");
    });
  });
});
