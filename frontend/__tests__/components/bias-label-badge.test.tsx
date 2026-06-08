import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BiasLabelBadge, {
  BIAS_STYLES,
} from "@/components/story/BiasLabelBadge";
import type { BiasLabel } from "@/lib/types";

describe("BiasLabelBadge", () => {
  const labels: BiasLabel[] = [
    "left",
    "center_left",
    "center",
    "center_right",
    "right",
    "unknown",
  ];

  it.each(labels)("renders correct text for %s", (label) => {
    render(<BiasLabelBadge label={label} />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent(
      BIAS_STYLES[label].text,
    );
  });

  it('renders "Left" with blue background', () => {
    const { container } = render(<BiasLabelBadge label="left" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-blue-600");
    expect(badge.className).toContain("text-white");
  });

  it('renders "Center-Left" with light blue background', () => {
    const { container } = render(<BiasLabelBadge label="center_left" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-blue-300");
  });

  it('renders "Center" with gray background', () => {
    const { container } = render(<BiasLabelBadge label="center" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-gray-200");
  });

  it('renders "Center-Right" with light red background', () => {
    const { container } = render(<BiasLabelBadge label="center_right" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-red-300");
  });

  it('renders "Right" with red background', () => {
    const { container } = render(<BiasLabelBadge label="right" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-red-600");
    expect(badge.className).toContain("text-white");
  });

  it('renders "Unknown" with muted gray style', () => {
    const { container } = render(<BiasLabelBadge label="unknown" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("bg-gray-100");
    expect(badge.className).toContain("text-gray-500");
  });

  it("renders as inline pill (rounded-full)", () => {
    const { container } = render(<BiasLabelBadge label="center" />);
    const badge = container.querySelector("[data-testid=bias-label]")!;
    expect(badge.className).toContain("rounded-full");
  });

  it("falls back to unknown style for unrecognized label", () => {
    // @ts-expect-error: testing invalid label fallback
    render(<BiasLabelBadge label="invalid_label" />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Unknown");
  });

  it("has all 6 bias labels in BIAS_STYLES", () => {
    expect(Object.keys(BIAS_STYLES)).toHaveLength(6);
    labels.forEach((l) => {
      expect(BIAS_STYLES[l]).toBeDefined();
      expect(BIAS_STYLES[l].text).toBeTruthy();
      expect(BIAS_STYLES[l].color).toBeTruthy();
    });
  });
});
