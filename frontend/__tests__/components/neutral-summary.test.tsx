import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import NeutralSummary from "@/components/story/NeutralSummary";

describe("NeutralSummary", () => {
  it("renders the summary text", () => {
    render(
      <NeutralSummary text="The Federal Reserve decided to maintain current interest rates." />,
    );
    expect(
      screen.getByText(
        "The Federal Reserve decided to maintain current interest rates.",
      ),
    ).toBeInTheDocument();
  });

  it('renders "Neutral Summary" heading', () => {
    render(<NeutralSummary text="Some text" />);
    expect(screen.getByText("Neutral Summary")).toBeInTheDocument();
  });

  it("renders heading as h2", () => {
    render(<NeutralSummary text="Some text" />);
    const heading = screen.getByText("Neutral Summary");
    expect(heading.tagName).toBe("H2");
  });

  it("renders text in a paragraph", () => {
    render(<NeutralSummary text="Paragraph content" />);
    const p = screen.getByText("Paragraph content");
    expect(p.tagName).toBe("P");
  });

  it("renders long text without truncation", () => {
    const longText = "A".repeat(500);
    render(<NeutralSummary text={longText} />);
    expect(screen.getByText(longText)).toBeInTheDocument();
  });

  it("wraps content in a section element", () => {
    const { container } = render(<NeutralSummary text="test" />);
    expect(container.querySelector("section")).toBeInTheDocument();
  });
});
