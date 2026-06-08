import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import GracePeriodWarning, {
  formatGraceDate,
} from "@/components/subscription/GracePeriodWarning";

describe("GracePeriodWarning", () => {
  const futureDate = "2026-07-15T00:00:00Z";

  it("renders the warning container", () => {
    render(
      <GracePeriodWarning
        proUntil={futureDate}
        onUpdatePayment={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId("grace-period-warning")).toBeInTheDocument();
  });

  it("shows the grace period date", () => {
    render(
      <GracePeriodWarning
        proUntil={futureDate}
        onUpdatePayment={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId("grace-message")).toHaveTextContent("July 15, 2026");
  });

  it("renders Update Payment Method button", () => {
    render(
      <GracePeriodWarning
        proUntil={futureDate}
        onUpdatePayment={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId("update-payment-btn")).toHaveTextContent(
      "Update Payment Method",
    );
  });

  it("calls onUpdatePayment when button clicked", () => {
    const onClick = vi.fn();
    render(
      <GracePeriodWarning
        proUntil={futureDate}
        onUpdatePayment={onClick}
        isLoading={false}
      />,
    );
    fireEvent.click(screen.getByTestId("update-payment-btn"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables button when loading", () => {
    render(
      <GracePeriodWarning
        proUntil={futureDate}
        onUpdatePayment={vi.fn()}
        isLoading={true}
      />,
    );
    expect(screen.getByTestId("update-payment-btn")).toBeDisabled();
  });
});

describe("formatGraceDate", () => {
  it("formats ISO date to human-readable string", () => {
    const result = formatGraceDate("2026-07-15T00:00:00Z");
    expect(result).toBe("July 15, 2026");
  });

  it("handles different dates", () => {
    const result = formatGraceDate("2026-01-01T12:00:00Z");
    expect(result).toBe("January 1, 2026");
  });
});
