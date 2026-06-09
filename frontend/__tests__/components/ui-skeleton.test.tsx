import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Skeleton, { ROUNDED_CLASSES } from "@/components/ui/Skeleton";

describe("Skeleton", () => {
  it("renders with default props", () => {
    render(<Skeleton />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("animate-pulse");
    expect(el.className).toContain("bg-gray-100");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("h-4");
  });

  it("applies custom height", () => {
    render(<Skeleton height="h-12" />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("h-12");
  });

  it("applies sm rounding", () => {
    render(<Skeleton rounded="sm" />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("rounded");
    expect(el.className).not.toContain("rounded-md");
  });

  it("applies lg rounding", () => {
    render(<Skeleton rounded="lg" />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("rounded-lg");
  });

  it("applies full rounding", () => {
    render(<Skeleton rounded="full" />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("rounded-full");
  });

  it("merges custom className", () => {
    render(<Skeleton className="w-24" />);
    const el = screen.getByTestId("ui-skeleton");
    expect(el.className).toContain("w-24");
  });

  it("has ui-skeleton test id", () => {
    render(<Skeleton />);
    expect(screen.getByTestId("ui-skeleton")).toBeInTheDocument();
  });
});

describe("ROUNDED_CLASSES", () => {
  it("has 4 rounding options", () => {
    expect(Object.keys(ROUNDED_CLASSES)).toHaveLength(4);
  });
});
