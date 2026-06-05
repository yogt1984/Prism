import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("email=test@example.com"),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import CheckEmailPage from "@/app/check-email/page";

describe("CheckEmailPage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  it("renders check email message", () => {
    render(<CheckEmailPage />);
    expect(screen.getByText("Check your inbox")).toBeInTheDocument();
    expect(screen.getByText(/test@example.com/)).toBeInTheDocument();
  });

  it("shows mail icon", () => {
    render(<CheckEmailPage />);
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders resend button", () => {
    render(<CheckEmailPage />);
    expect(
      screen.getByText(/Didn\u2019t get it\? Resend/),
    ).toBeInTheDocument();
  });

  it("starts 60s cooldown after clicking resend", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CheckEmailPage />);

    const resend = screen.getByText(/Resend/);
    await user.click(resend);

    expect(screen.getByText(/Resend in 60s/)).toBeInTheDocument();
    expect(screen.getByText(/Resend in 60s/)).toBeDisabled();
  });

  it("counts down the cooldown timer", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CheckEmailPage />);

    await user.click(screen.getByText(/Resend/));

    // Advance past the full 60s cooldown
    for (let i = 0; i < 61; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }

    expect(screen.getByText(/Didn\u2019t get it\? Resend/)).toBeEnabled();
  });

  it("calls fetch to resend email", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CheckEmailPage />);

    await user.click(screen.getByText(/Resend/));

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/auth/signin/email",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("test@example.com"),
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
