import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import QueryProvider from "@/components/providers/QueryProvider";

function TestChild() {
  const queryClient = useQueryClient();
  return (
    <div data-testid="has-client">
      {queryClient ? "connected" : "disconnected"}
    </div>
  );
}

describe("QueryProvider", () => {
  it("provides QueryClient to children", () => {
    render(
      <QueryProvider>
        <TestChild />
      </QueryProvider>,
    );
    expect(screen.getByTestId("has-client")).toHaveTextContent("connected");
  });

  it("renders children", () => {
    render(
      <QueryProvider>
        <div data-testid="child">Hello</div>
      </QueryProvider>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders multiple children", () => {
    render(
      <QueryProvider>
        <div data-testid="a">A</div>
        <div data-testid="b">B</div>
      </QueryProvider>,
    );
    expect(screen.getByTestId("a")).toBeInTheDocument();
    expect(screen.getByTestId("b")).toBeInTheDocument();
  });
});
