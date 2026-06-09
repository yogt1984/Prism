import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Badge, { SIZE_CLASSES } from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies default sm size classes", () => {
    render(<Badge>Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("px-2");
    expect(el.className).toContain("py-0.5");
    expect(el.className).toContain("text-xs");
  });

  it("applies md size classes", () => {
    render(<Badge size="md">Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("px-3");
    expect(el.className).toContain("py-1");
    expect(el.className).toContain("text-sm");
  });

  it("applies default color when none specified", () => {
    render(<Badge>Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("bg-gray-100");
    expect(el.className).toContain("text-gray-600");
  });

  it("applies custom color", () => {
    render(<Badge color="bg-violet-100 text-violet-700">Pro</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("bg-violet-100");
    expect(el.className).toContain("text-violet-700");
  });

  it("passes through additional className", () => {
    render(<Badge className="gap-1">Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("gap-1");
  });

  it("allows data-testid override", () => {
    render(<Badge data-testid="custom-badge">Tag</Badge>);
    expect(screen.getByTestId("custom-badge")).toBeInTheDocument();
  });

  it("always has rounded-full and font-medium", () => {
    render(<Badge>Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("rounded-full");
    expect(el.className).toContain("font-medium");
  });

  it("uses inline-flex items-center display", () => {
    render(<Badge>Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.className).toContain("inline-flex");
    expect(el.className).toContain("items-center");
  });

  it("renders as a span element", () => {
    render(<Badge>Tag</Badge>);
    const el = screen.getByTestId("ui-badge");
    expect(el.tagName).toBe("SPAN");
  });

  it("exports SIZE_CLASSES constant", () => {
    expect(SIZE_CLASSES.sm).toBe("px-2 py-0.5 text-xs");
    expect(SIZE_CLASSES.md).toBe("px-3 py-1 text-sm");
  });
});
