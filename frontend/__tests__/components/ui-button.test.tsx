import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Button, { VARIANT_CLASSES, SIZE_CLASSES } from "@/components/ui/Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("has ui-button test id", () => {
    render(<Button>Test</Button>);
    expect(screen.getByTestId("ui-button")).toBeInTheDocument();
  });

  it("defaults to primary variant and md size", () => {
    render(<Button>Default</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("bg-violet-600");
    expect(btn.className).toContain("px-4");
  });

  it("applies primary variant", () => {
    render(<Button variant="primary">Primary</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("bg-violet-600");
    expect(btn.className).toContain("text-white");
  });

  it("applies secondary variant", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("border-gray-300");
    expect(btn.className).toContain("text-gray-700");
  });

  it("applies ghost variant", () => {
    render(<Button variant="ghost">Ghost</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("text-violet-600");
  });

  it("applies danger variant", () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("bg-amber-600");
  });

  it("applies sm size", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("px-3");
    expect(btn.className).toContain("text-xs");
  });

  it("applies fullWidth", () => {
    render(<Button fullWidth>Full</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("w-full");
  });

  it("passes disabled state", () => {
    render(<Button disabled>Disabled</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn).toBeDisabled();
    expect(btn.className).toContain("disabled:opacity-50");
  });

  it("fires onClick", () => {
    const handler = vi.fn();
    render(<Button onClick={handler}>Click</Button>);
    fireEvent.click(screen.getByTestId("ui-button"));
    expect(handler).toHaveBeenCalledOnce();
  });

  it("merges custom className", () => {
    render(<Button className="mt-4">Custom</Button>);
    const btn = screen.getByTestId("ui-button");
    expect(btn.className).toContain("mt-4");
  });

  it("passes through HTML attributes", () => {
    render(<Button type="submit">Submit</Button>);
    expect(screen.getByTestId("ui-button")).toHaveAttribute("type", "submit");
  });
});

describe("VARIANT_CLASSES", () => {
  it("has 4 variants", () => {
    expect(Object.keys(VARIANT_CLASSES)).toHaveLength(4);
  });
});

describe("SIZE_CLASSES", () => {
  it("has 2 sizes", () => {
    expect(Object.keys(SIZE_CLASSES)).toHaveLength(2);
  });
});
