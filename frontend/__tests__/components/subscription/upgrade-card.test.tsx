import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import UpgradeCard, { FEATURES } from "@/components/subscription/UpgradeCard";

describe("UpgradeCard", () => {
  it("renders all Pro features", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={false} />);
    for (const feature of FEATURES) {
      expect(screen.getByText(feature)).toBeInTheDocument();
    }
  });

  it("renders upgrade card container", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={false} />);
    expect(screen.getByTestId("upgrade-card")).toBeInTheDocument();
  });

  it("renders price", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={false} />);
    expect(screen.getByText("$7")).toBeInTheDocument();
    expect(screen.getByText("/month")).toBeInTheDocument();
  });

  it("shows 'Upgrade Now' when not loading", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={false} />);
    expect(screen.getByTestId("upgrade-btn")).toHaveTextContent("Upgrade Now");
    expect(screen.getByTestId("upgrade-btn")).not.toBeDisabled();
  });

  it("shows 'Redirecting to payment...' when loading", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={true} />);
    expect(screen.getByTestId("upgrade-btn")).toHaveTextContent(
      "Redirecting to payment...",
    );
    expect(screen.getByTestId("upgrade-btn")).toBeDisabled();
  });

  it("calls onUpgrade when clicked", () => {
    const onUpgrade = vi.fn();
    render(<UpgradeCard onUpgrade={onUpgrade} isLoading={false} />);
    fireEvent.click(screen.getByTestId("upgrade-btn"));
    expect(onUpgrade).toHaveBeenCalledOnce();
  });

  it("does not call onUpgrade when disabled", () => {
    const onUpgrade = vi.fn();
    render(<UpgradeCard onUpgrade={onUpgrade} isLoading={true} />);
    fireEvent.click(screen.getByTestId("upgrade-btn"));
    expect(onUpgrade).not.toHaveBeenCalled();
  });

  it("renders 5 features", () => {
    render(<UpgradeCard onUpgrade={vi.fn()} isLoading={false} />);
    expect(screen.getByTestId("feature-list").children).toHaveLength(5);
  });
});
