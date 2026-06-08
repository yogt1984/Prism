import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TimeRangeSelector, {
  OPTIONS,
} from "@/components/perception/TimeRangeSelector";

describe("TimeRangeSelector", () => {
  it("renders all 3 options", () => {
    render(<TimeRangeSelector value="7d" onChange={() => {}} />);
    expect(screen.getByTestId("time-range-24h")).toBeInTheDocument();
    expect(screen.getByTestId("time-range-7d")).toBeInTheDocument();
    expect(screen.getByTestId("time-range-30d")).toBeInTheDocument();
  });

  it("applies active style to selected option", () => {
    render(<TimeRangeSelector value="7d" onChange={() => {}} />);
    const active = screen.getByTestId("time-range-7d");
    expect(active.className).toContain("bg-violet-600");
    expect(active.className).toContain("text-white");
  });

  it("applies inactive style to non-selected options", () => {
    render(<TimeRangeSelector value="7d" onChange={() => {}} />);
    const inactive = screen.getByTestId("time-range-24h");
    expect(inactive.className).toContain("bg-gray-100");
    expect(inactive.className).toContain("text-gray-600");
  });

  it("calls onChange with correct value on click", () => {
    const onChange = vi.fn();
    render(<TimeRangeSelector value="7d" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("time-range-24h"));
    expect(onChange).toHaveBeenCalledWith("24h");
  });

  it("calls onChange for 30d", () => {
    const onChange = vi.fn();
    render(<TimeRangeSelector value="7d" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("time-range-30d"));
    expect(onChange).toHaveBeenCalledWith("30d");
  });

  it("sets aria-pressed correctly", () => {
    render(<TimeRangeSelector value="24h" onChange={() => {}} />);
    expect(screen.getByTestId("time-range-24h")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("time-range-7d")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("time-range-30d")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("has container with correct test id", () => {
    render(<TimeRangeSelector value="7d" onChange={() => {}} />);
    expect(screen.getByTestId("time-range-selector")).toBeInTheDocument();
  });

  it("OPTIONS constant has correct values", () => {
    expect(OPTIONS).toHaveLength(3);
    expect(OPTIONS.map((o) => o.value)).toEqual(["24h", "7d", "30d"]);
  });
});
