import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Pagination from "@/components/briefing/Pagination";

describe("Pagination", () => {
  it("renders page 1 with offset 0", () => {
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-info")).toHaveTextContent("Page 1");
  });

  it("renders page 2 with offset 20", () => {
    render(
      <Pagination
        offset={20}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-info")).toHaveTextContent("Page 2");
  });

  it("disables Previous on first page", () => {
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
  });

  it("enables Previous on page 2+", () => {
    render(
      <Pagination
        offset={20}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-prev")).not.toBeDisabled();
  });

  it("disables Next when fewer items than page size", () => {
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={10}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("enables Next when full page returned", () => {
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-next")).not.toBeDisabled();
  });

  it("calls onPrevious when Previous clicked", () => {
    const onPrevious = vi.fn();
    render(
      <Pagination
        offset={20}
        pageSize={20}
        itemCount={20}
        onPrevious={onPrevious}
        onNext={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("pagination-prev"));
    expect(onPrevious).toHaveBeenCalledTimes(1);
  });

  it("calls onNext when Next clicked", () => {
    const onNext = vi.fn();
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={20}
        onPrevious={vi.fn()}
        onNext={onNext}
      />,
    );
    fireEvent.click(screen.getByTestId("pagination-next"));
    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("does not call onPrevious when disabled", () => {
    const onPrevious = vi.fn();
    render(
      <Pagination
        offset={0}
        pageSize={20}
        itemCount={20}
        onPrevious={onPrevious}
        onNext={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("pagination-prev"));
    expect(onPrevious).not.toHaveBeenCalled();
  });

  it("renders page 3 with offset 40 and pageSize 20", () => {
    render(
      <Pagination
        offset={40}
        pageSize={20}
        itemCount={5}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pagination-info")).toHaveTextContent("Page 3");
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
    expect(screen.getByTestId("pagination-prev")).not.toBeDisabled();
  });
});
