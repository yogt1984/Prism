import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SentBadge from "@/components/briefing/SentBadge";

describe("SentBadge", () => {
  it('shows "Sent" with green style when sent is true', () => {
    render(<SentBadge sent={true} />);
    const el = screen.getByTestId("sent-badge");
    expect(el).toHaveTextContent("Sent");
    expect(el.className).toContain("bg-green-100");
    expect(el.className).toContain("text-green-700");
  });

  it('shows "Draft" with yellow style when sent is false', () => {
    render(<SentBadge sent={false} />);
    const el = screen.getByTestId("sent-badge");
    expect(el).toHaveTextContent("Draft");
    expect(el.className).toContain("bg-yellow-100");
    expect(el.className).toContain("text-yellow-700");
  });
});
