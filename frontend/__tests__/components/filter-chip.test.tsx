import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FilterChip from "@/components/sources/FilterChip";

describe("FilterChip", () => {
  it("renders the label text", () => {
    render(<FilterChip label="Left" active={false} onClick={() => {}} />);
    expect(screen.getByText("Left")).toBeInTheDocument();
  });

  it("has correct test id from label", () => {
    render(<FilterChip label="Center-Left" active={false} onClick={() => {}} />);
    expect(screen.getByTestId("filter-chip-center-left")).toBeInTheDocument();
  });

  it("applies active styles when active", () => {
    render(<FilterChip label="All" active={true} onClick={() => {}} />);
    const btn = screen.getByTestId("filter-chip-all");
    expect(btn.className).toContain("bg-gray-800");
    expect(btn.className).toContain("text-white");
  });

  it("applies inactive styles when not active", () => {
    render(<FilterChip label="All" active={false} onClick={() => {}} />);
    const btn = screen.getByTestId("filter-chip-all");
    expect(btn.className).toContain("bg-white");
    expect(btn.className).toContain("text-gray-600");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<FilterChip label="Left" active={false} onClick={onClick} />);
    fireEvent.click(screen.getByText("Left"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders color dot when color prop provided", () => {
    render(
      <FilterChip
        label="Left"
        active={false}
        onClick={() => {}}
        color="bg-blue-600"
      />,
    );
    const dot = screen.getByTestId("chip-dot");
    expect(dot.className).toContain("bg-blue-600");
  });

  it("does not render color dot when no color prop", () => {
    render(<FilterChip label="All" active={false} onClick={() => {}} />);
    expect(screen.queryByTestId("chip-dot")).toBeNull();
  });

  it("sets aria-pressed to true when active", () => {
    render(<FilterChip label="Left" active={true} onClick={() => {}} />);
    expect(screen.getByTestId("filter-chip-left")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("sets aria-pressed to false when inactive", () => {
    render(<FilterChip label="Left" active={false} onClick={() => {}} />);
    expect(screen.getByTestId("filter-chip-left")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("is a button element", () => {
    render(<FilterChip label="Left" active={false} onClick={() => {}} />);
    expect(screen.getByRole("button", { name: "Left" })).toBeInTheDocument();
  });
});
