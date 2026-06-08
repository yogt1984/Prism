import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DepthSlider from "@/components/settings/DepthSlider";

describe("DepthSlider", () => {
  it("renders the slider", () => {
    render(
      <DepthSlider value={10} onChange={vi.fn()} min={1} max={25} />,
    );
    expect(screen.getByTestId("depth-slider")).toBeInTheDocument();
  });

  it("displays current value", () => {
    render(
      <DepthSlider value={10} onChange={vi.fn()} min={1} max={25} />,
    );
    expect(screen.getByTestId("depth-value")).toHaveTextContent(
      "10 stories",
    );
  });

  it('shows "1 story" for singular', () => {
    render(
      <DepthSlider value={1} onChange={vi.fn()} min={1} max={10} />,
    );
    expect(screen.getByTestId("depth-value")).toHaveTextContent("1 story");
  });

  it("sets correct min/max on range input", () => {
    render(
      <DepthSlider value={5} onChange={vi.fn()} min={1} max={10} />,
    );
    const input = screen.getByTestId("depth-range");
    expect(input).toHaveAttribute("min", "1");
    expect(input).toHaveAttribute("max", "10");
  });

  it("calls onChange with new value", () => {
    const onChange = vi.fn();
    render(
      <DepthSlider value={5} onChange={onChange} min={1} max={25} />,
    );
    fireEvent.change(screen.getByTestId("depth-range"), {
      target: { value: "15" },
    });
    expect(onChange).toHaveBeenCalledWith(15);
  });

  it("renders min and max labels", () => {
    render(
      <DepthSlider value={5} onChange={vi.fn()} min={1} max={25} />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("sets correct value on range input", () => {
    render(
      <DepthSlider value={7} onChange={vi.fn()} min={1} max={10} />,
    );
    expect(screen.getByTestId("depth-range")).toHaveValue("7");
  });

  it("respects free-tier max of 10", () => {
    render(
      <DepthSlider value={10} onChange={vi.fn()} min={1} max={10} />,
    );
    expect(screen.getByTestId("depth-range")).toHaveAttribute("max", "10");
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("respects pro-tier max of 25", () => {
    render(
      <DepthSlider value={20} onChange={vi.fn()} min={1} max={25} />,
    );
    expect(screen.getByTestId("depth-range")).toHaveAttribute("max", "25");
  });
});
