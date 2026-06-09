import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Card, { VARIANT_CLASSES } from "@/components/ui/Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Content</Card>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("has ui-card test id", () => {
    render(<Card>Test</Card>);
    expect(screen.getByTestId("ui-card")).toBeInTheDocument();
  });

  it("defaults to default variant", () => {
    render(<Card>Default</Card>);
    const card = screen.getByTestId("ui-card");
    expect(card.className).toContain("border-gray-200");
    expect(card.className).toContain("p-4");
  });

  it("applies large variant", () => {
    render(<Card variant="large">Large</Card>);
    const card = screen.getByTestId("ui-card");
    expect(card.className).toContain("p-6");
  });

  it("applies alert variant", () => {
    render(<Card variant="alert">Alert</Card>);
    const card = screen.getByTestId("ui-card");
    expect(card.className).toContain("bg-violet-50");
    expect(card.className).toContain("border-violet-200");
  });

  it("applies success variant", () => {
    render(<Card variant="success">Success</Card>);
    const card = screen.getByTestId("ui-card");
    expect(card.className).toContain("bg-green-50");
    expect(card.className).toContain("border-green-200");
  });

  it("merges custom className", () => {
    render(<Card className="space-y-4">Custom</Card>);
    const card = screen.getByTestId("ui-card");
    expect(card.className).toContain("space-y-4");
  });

  it("passes through HTML attributes", () => {
    render(<Card data-custom="val">Attrs</Card>);
    expect(screen.getByTestId("ui-card")).toHaveAttribute("data-custom", "val");
  });
});

describe("VARIANT_CLASSES", () => {
  it("has 4 variants", () => {
    expect(Object.keys(VARIANT_CLASSES)).toHaveLength(4);
  });
});
