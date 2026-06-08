import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import InterestToggle from "@/components/settings/InterestToggle";

describe("InterestToggle", () => {
  it("renders category name", () => {
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("interest-toggle-finance"),
    ).toHaveTextContent("finance");
  });

  it("renders as selected with blue styling", () => {
    render(
      <InterestToggle
        category="finance"
        selected={true}
        onToggle={vi.fn()}
      />,
    );
    const el = screen.getByTestId("interest-toggle-finance");
    expect(el.className).toContain("bg-blue-50");
    expect(el.className).toContain("border-blue-500");
  });

  it("renders as unselected with white/gray styling", () => {
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={vi.fn()}
      />,
    );
    const el = screen.getByTestId("interest-toggle-finance");
    expect(el.className).toContain("bg-white");
    expect(el.className).toContain("border-gray-200");
  });

  it("shows check icon when selected", () => {
    render(
      <InterestToggle
        category="finance"
        selected={true}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByTestId("check-icon")).toBeInTheDocument();
  });

  it("does not show check icon when unselected", () => {
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("check-icon")).not.toBeInTheDocument();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByTestId("interest-toggle-finance"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("does not call onToggle when disabled", () => {
    const onToggle = vi.fn();
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={onToggle}
        disabled
      />,
    );
    fireEvent.click(screen.getByTestId("interest-toggle-finance"));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("applies disabled styling", () => {
    render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={vi.fn()}
        disabled
      />,
    );
    const el = screen.getByTestId("interest-toggle-finance");
    expect(el.className).toContain("opacity-50");
    expect(el.className).toContain("cursor-not-allowed");
    expect(el).toBeDisabled();
  });

  it("sets aria-pressed attribute", () => {
    const { rerender } = render(
      <InterestToggle
        category="finance"
        selected={false}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("interest-toggle-finance"),
    ).toHaveAttribute("aria-pressed", "false");

    rerender(
      <InterestToggle
        category="finance"
        selected={true}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("interest-toggle-finance"),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("capitalizes category name", () => {
    render(
      <InterestToggle
        category="technology"
        selected={false}
        onToggle={vi.fn()}
      />,
    );
    const el = screen.getByTestId("interest-toggle-technology");
    expect(el.className).toContain("capitalize");
  });
});
