import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-auth/react", () => ({
  SessionProvider: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="session-provider">{children}</div>,
}));

import AuthProvider from "@/components/providers/AuthProvider";

describe("AuthProvider", () => {
  it("renders children inside SessionProvider", () => {
    render(
      <AuthProvider>
        <p>test child</p>
      </AuthProvider>,
    );

    expect(screen.getByTestId("session-provider")).toBeInTheDocument();
    expect(screen.getByText("test child")).toBeInTheDocument();
  });

  it("renders multiple children", () => {
    render(
      <AuthProvider>
        <p>child 1</p>
        <p>child 2</p>
      </AuthProvider>,
    );

    expect(screen.getByText("child 1")).toBeInTheDocument();
    expect(screen.getByText("child 2")).toBeInTheDocument();
  });
});
