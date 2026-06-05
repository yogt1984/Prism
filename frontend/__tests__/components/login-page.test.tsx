import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Must use vi.hoisted so the mock factory can reference it
const { mockSignIn } = vi.hoisted(() => ({
  mockSignIn: vi.fn(),
}));
vi.mock("next-auth/react", () => ({
  signIn: mockSignIn,
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    mockSignIn.mockReset();
    // Mock window.location
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
    });
  });

  it("renders login form", () => {
    render(<LoginPage />);
    expect(screen.getByText("Log in to Prism")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send magic link/i }),
    ).toBeInTheDocument();
  });

  it("shows link to signup page", () => {
    render(<LoginPage />);
    const link = screen.getByText("Create account");
    expect(link).toHaveAttribute("href", "/signup");
  });

  it("shows error for invalid email format", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email");
    const submit = screen.getByRole("button", { name: /send magic link/i });

    await user.type(emailInput, "notanemail");
    await user.click(submit);

    expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid email");
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("shows error for empty email", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const submit = screen.getByRole("button", { name: /send magic link/i });
    await user.click(submit);

    expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid email");
  });

  it("calls signIn with valid email", async () => {
    mockSignIn.mockResolvedValueOnce({ error: null });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith("email", {
        email: "test@example.com",
        callbackUrl: "/dashboard",
        redirect: false,
      });
    });
  });

  it("normalizes email to lowercase trimmed", async () => {
    mockSignIn.mockResolvedValueOnce({ error: null });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "  TEST@Example.COM  ");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith(
        "email",
        expect.objectContaining({ email: "test@example.com" }),
      );
    });
  });

  it("redirects to /check-email on success", async () => {
    mockSignIn.mockResolvedValueOnce({ error: null });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    await waitFor(() => {
      expect(window.location.href).toBe("/check-email");
    });
  });

  it("shows error when signIn fails", async () => {
    mockSignIn.mockResolvedValueOnce({ error: "EmailSignin" });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not send magic link",
      );
    });
  });

  it("shows error on network failure", async () => {
    mockSignIn.mockRejectedValueOnce(new Error("Network error"));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("unavailable");
    });
  });

  it("disables button while loading", async () => {
    let resolveSignIn: (v: unknown) => void;
    mockSignIn.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSignIn = resolve;
      }),
    );
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /send magic link/i }),
    );

    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByRole("button")).toHaveTextContent("Sending...");

    resolveSignIn!({ error: null });
  });
});
