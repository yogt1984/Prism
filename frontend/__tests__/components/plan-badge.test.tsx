import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PlanBadge from "@/components/settings/PlanBadge";

describe("PlanBadge", () => {
  it('renders "Free" with gray styling', () => {
    render(<PlanBadge tier="Free" />);
    const el = screen.getByTestId("plan-badge");
    expect(el).toHaveTextContent("Free");
    expect(el.className).toContain("bg-gray-100");
  });

  it('renders "Pro" with violet styling', () => {
    render(<PlanBadge tier="Pro" />);
    const el = screen.getByTestId("plan-badge");
    expect(el).toHaveTextContent("Pro");
    expect(el.className).toContain("bg-violet-100");
    expect(el.className).toContain("text-violet-700");
  });
});
