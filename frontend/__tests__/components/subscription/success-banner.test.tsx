import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import SuccessBanner from "@/components/subscription/SuccessBanner";

describe("SuccessBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the success banner", () => {
    render(<SuccessBanner onDismiss={vi.fn()} />);
    expect(screen.getByTestId("success-banner")).toBeInTheDocument();
  });

  it("shows welcome message", () => {
    render(<SuccessBanner onDismiss={vi.fn()} />);
    expect(screen.getByText("Welcome to Prism Pro!")).toBeInTheDocument();
    expect(
      screen.getByText("All Pro features are now active."),
    ).toBeInTheDocument();
  });

  it("auto-dismisses after default timeout (8s)", () => {
    const onDismiss = vi.fn();
    render(<SuccessBanner onDismiss={onDismiss} />);

    expect(screen.getByTestId("success-banner")).toBeInTheDocument();
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(8000);
    });

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(screen.queryByTestId("success-banner")).not.toBeInTheDocument();
  });

  it("auto-dismisses after custom timeout", () => {
    const onDismiss = vi.fn();
    render(<SuccessBanner onDismiss={onDismiss} autoHideMs={3000} />);

    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("dismisses on manual click", () => {
    const onDismiss = vi.fn();
    render(<SuccessBanner onDismiss={onDismiss} />);

    fireEvent.click(screen.getByTestId("dismiss-banner"));
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(screen.queryByTestId("success-banner")).not.toBeInTheDocument();
  });

  it("renders dismiss button", () => {
    render(<SuccessBanner onDismiss={vi.fn()} />);
    expect(screen.getByTestId("dismiss-banner")).toHaveTextContent("Dismiss");
  });
});
