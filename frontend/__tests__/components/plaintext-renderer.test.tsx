import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PlainTextRenderer from "@/components/briefing/PlainTextRenderer";

describe("PlainTextRenderer", () => {
  it("renders text content", () => {
    render(<PlainTextRenderer text="Morning Briefing" />);
    expect(screen.getByTestId("plaintext-renderer")).toHaveTextContent(
      "Morning Briefing",
    );
  });

  it("uses a pre element", () => {
    render(<PlainTextRenderer text="Text" />);
    expect(screen.getByTestId("plaintext-renderer").tagName).toBe("PRE");
  });

  it("preserves whitespace and newlines", () => {
    const text = "Line 1\n\nLine 2\n  Indented";
    render(<PlainTextRenderer text={text} />);
    const el = screen.getByTestId("plaintext-renderer");
    expect(el.className).toContain("whitespace-pre-wrap");
    expect(el.textContent).toBe(text);
  });

  it("renders empty string without error", () => {
    render(<PlainTextRenderer text="" />);
    expect(screen.getByTestId("plaintext-renderer").textContent).toBe("");
  });

  it("renders long text", () => {
    const long = "A".repeat(1000);
    render(<PlainTextRenderer text={long} />);
    expect(screen.getByTestId("plaintext-renderer").textContent).toBe(long);
  });
});
