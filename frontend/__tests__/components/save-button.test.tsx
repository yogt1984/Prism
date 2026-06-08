import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SaveButton from "@/components/settings/SaveButton";

describe("SaveButton", () => {
  it('renders "Save" by default', () => {
    render(<SaveButton onClick={vi.fn()} disabled={false} />);
    expect(screen.getByTestId("save-btn")).toHaveTextContent("Save");
  });

  it("renders custom label", () => {
    render(
      <SaveButton onClick={vi.fn()} disabled={false} label="Update" />,
    );
    expect(screen.getByTestId("save-btn")).toHaveTextContent("Update");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<SaveButton onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByTestId("save-btn"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when disabled prop is true", () => {
    render(<SaveButton onClick={vi.fn()} disabled={true} />);
    expect(screen.getByTestId("save-btn")).toBeDisabled();
  });

  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(<SaveButton onClick={onClick} disabled={true} />);
    fireEvent.click(screen.getByTestId("save-btn"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('shows "Saving..." when isPending', () => {
    render(
      <SaveButton onClick={vi.fn()} disabled={false} isPending={true} />,
    );
    expect(screen.getByTestId("save-btn")).toHaveTextContent("Saving...");
  });

  it("is disabled when isPending", () => {
    render(
      <SaveButton onClick={vi.fn()} disabled={false} isPending={true} />,
    );
    expect(screen.getByTestId("save-btn")).toBeDisabled();
  });
});
