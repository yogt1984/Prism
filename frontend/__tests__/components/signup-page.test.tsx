import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockSignIn } = vi.hoisted(() => ({
  mockSignIn: vi.fn(),
}));
vi.mock("next-auth/react", () => ({
  signIn: mockSignIn,
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
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

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import SignupPage from "@/app/signup/page";

describe("SignupPage", () => {
  beforeEach(() => {
    mockSignIn.mockReset();
    mockFetch.mockReset();
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
    });
  });

  it("renders signup form with all interest chips", () => {
    render(<SignupPage />);
    expect(screen.getByText("Create your Prism account")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("Politics")).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
    expect(screen.getByText("Sports")).toBeInTheDocument();
    expect(screen.getByText("Culture")).toBeInTheDocument();
    expect(screen.getByText("Science")).toBeInTheDocument();
    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("World")).toBeInTheDocument();
  });

  it("shows link to login page", () => {
    render(<SignupPage />);
    expect(screen.getByText("Log in")).toHaveAttribute("href", "/login");
  });

  it("toggles interest selection", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    const finance = screen.getByLabelText("Finance");
    expect(finance).toHaveAttribute("aria-checked", "false");

    await user.click(finance);
    expect(finance).toHaveAttribute("aria-checked", "true");

    await user.click(finance);
    expect(finance).toHaveAttribute("aria-checked", "false");
  });

  it("shows error for invalid email", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "bad");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid email");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows error when no interests selected", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Select at least one interest",
    );
  });

  it("creates account and sends magic link on success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1, email: "test@example.com" }),
    });
    mockSignIn.mockResolvedValueOnce({ error: null });

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(screen.getByLabelText("Technology"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/signup",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("test@example.com"),
        }),
      );
    });

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith(
        "email",
        expect.objectContaining({ email: "test@example.com" }),
      );
    });

    await waitFor(() => {
      expect(window.location.href).toBe("/check-email");
    });
  });

  it("shows duplicate email error on 422", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Email already registered" }),
    });

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "dup@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Account exists",
      );
    });
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("shows generic error on API failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Server error" }),
    });

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Server error");
    });
  });

  it("shows unavailable error on network failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("unavailable");
    });
  });

  it("normalizes email to lowercase", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });
    mockSignIn.mockResolvedValueOnce({ error: null });

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "TEST@Example.COM");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/signup",
        expect.objectContaining({
          body: expect.stringContaining("test@example.com"),
        }),
      );
    });
  });

  it("disables button while loading", async () => {
    let resolveFetch: (v: unknown) => void;
    mockFetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();

    resolveFetch!({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });
  });

  it("allows selecting multiple interests", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });
    mockSignIn.mockResolvedValueOnce({ error: null });

    const user = userEvent.setup();
    render(<SignupPage />);

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.click(screen.getByLabelText("Finance"));
    await user.click(screen.getByLabelText("Sports"));
    await user.click(screen.getByLabelText("Science"));
    await user.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    await waitFor(() => {
      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.interests).toEqual(["finance", "sports", "science"]);
    });
  });
});
