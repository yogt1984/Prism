import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PerspectiveCard from "@/components/story/PerspectiveCard";
import { makePerspective, makeSource } from "../helpers/fixtures";

describe("PerspectiveCard", () => {
  it("renders the card container", () => {
    const p = makePerspective();
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByTestId("perspective-card")).toBeInTheDocument();
  });

  it("displays source name when source provided", () => {
    const p = makePerspective({ source_id: 1 });
    const source = makeSource({ id: 1, name: "Reuters" });
    render(<PerspectiveCard perspective={p} source={source} />);
    expect(screen.getByText("Reuters")).toBeInTheDocument();
  });

  it("falls back to Source #id when no source provided", () => {
    const p = makePerspective({ source_id: 99 });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByText("Source #99")).toBeInTheDocument();
  });

  it("renders bias label badge", () => {
    const p = makePerspective({ bias_label: "left" });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Left");
  });

  it("renders sentiment bar", () => {
    const p = makePerspective({ sentiment: 0.5 });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByTestId("sentiment-bar")).toBeInTheDocument();
  });

  it("renders summary text", () => {
    const p = makePerspective({
      summary: "The Fed held rates steady.",
    });
    render(<PerspectiveCard perspective={p} />);
    expect(
      screen.getByText("The Fed held rates steady."),
    ).toBeInTheDocument();
  });

  it("renders key claims when valid JSON", () => {
    const p = makePerspective({
      key_claims: JSON.stringify(["Claim A", "Claim B"]),
    });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByText("Claim A")).toBeInTheDocument();
    expect(screen.getByText("Claim B")).toBeInTheDocument();
  });

  it("does not render key claims for invalid JSON", () => {
    const p = makePerspective({ key_claims: "invalid" });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.queryByTestId("key-claims")).not.toBeInTheDocument();
  });

  it("does not render key claims for empty array", () => {
    const p = makePerspective({ key_claims: "[]" });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.queryByTestId("key-claims")).not.toBeInTheDocument();
  });

  it("renders with center bias label", () => {
    const p = makePerspective({ bias_label: "center" });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Center");
  });

  it("renders with right bias label", () => {
    const p = makePerspective({ bias_label: "right" });
    render(<PerspectiveCard perspective={p} />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Right");
  });

  it("renders negative sentiment correctly", () => {
    const p = makePerspective({ sentiment: -0.8 });
    render(<PerspectiveCard perspective={p} />);
    const bar = screen.getByTestId("sentiment-bar");
    expect(bar).toHaveAttribute("aria-label", "Sentiment: -0.80");
  });
});
