import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Will be overridden per test via mockReturnValue
const mockGet = vi.fn();
vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mockGet }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import AuthErrorPage from "@/app/auth-error/page";

describe("AuthErrorPage", () => {
  it("shows EmailSignin error with try again", () => {
    mockGet.mockReturnValue("EmailSignin");
    render(<AuthErrorPage />);

    expect(screen.getByText("Could not send magic link")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toHaveAttribute("href", "/login");
  });

  it("shows Verification error with request new link", () => {
    mockGet.mockReturnValue("Verification");
    render(<AuthErrorPage />);

    expect(
      screen.getByText("Link expired or already used"),
    ).toBeInTheDocument();
    expect(screen.getByText("Request new link")).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows AccessDenied error with create account link", () => {
    mockGet.mockReturnValue("AccessDenied");
    render(<AuthErrorPage />);

    expect(screen.getByText("No account found")).toBeInTheDocument();
    expect(screen.getByText("Create account")).toHaveAttribute(
      "href",
      "/signup",
    );
  });

  it("shows default error for unknown error code", () => {
    mockGet.mockReturnValue("SomeRandomError");
    render(<AuthErrorPage />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Back to login")).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows default error when no error param", () => {
    mockGet.mockReturnValue(null);
    render(<AuthErrorPage />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders error icon", () => {
    mockGet.mockReturnValue("EmailSignin");
    render(<AuthErrorPage />);

    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("shows descriptive text for each error", () => {
    mockGet.mockReturnValue("Verification");
    render(<AuthErrorPage />);

    expect(
      screen.getByText(/single-use and expire/),
    ).toBeInTheDocument();
  });
});
