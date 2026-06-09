import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Sidebar from "@/components/dashboard/Sidebar";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
  });

  it("shows user name from session", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    renderWithQuery(<Sidebar />);
    expect(screen.getByTestId("user-greeting")).toHaveTextContent("Alice");
  });

  it("falls back to email prefix when no name", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: null, email: "bob@example.com" } },
    });
    renderWithQuery(<Sidebar />);
    expect(screen.getByTestId("user-greeting")).toHaveTextContent("bob");
  });

  it("falls back to 'there' when no session data", () => {
    mockUseSession.mockReturnValue({ data: null });
    renderWithQuery(<Sidebar />);
    expect(screen.getByTestId("user-greeting")).toHaveTextContent("there");
  });

  it("renders Generate briefing button", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    renderWithQuery(<Sidebar />);
    expect(screen.getByText("Generate briefing")).toBeInTheDocument();
  });

  it("calls onTriggerBriefing when button clicked", async () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    const onTrigger = vi.fn();
    const user = userEvent.setup();
    renderWithQuery(<Sidebar onTriggerBriefing={onTrigger} />);

    await user.click(screen.getByText("Generate briefing"));
    expect(onTrigger).toHaveBeenCalledOnce();
  });

  it("shows Generating... when pending", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    renderWithQuery(<Sidebar isTriggerPending={true} />);
    expect(screen.getByText("Generating...")).toBeDisabled();
  });

  it("renders Welcome back text", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    renderWithQuery(<Sidebar />);
    expect(screen.getByText("Welcome back,")).toBeInTheDocument();
  });

  it("has sidebar testid", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice", email: "alice@example.com" } },
    });
    renderWithQuery(<Sidebar />);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  it("shows upgrade link for free users", async () => {
    mockUseSession.mockReturnValue({
      data: { user: { id: 5, name: "Alice", email: "alice@example.com" } },
    });
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/users/5")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 5,
            email: "alice@example.com",
            name: "Alice",
            interests: "finance",
            preferred_format: "email",
            briefing_depth: 10,
            is_pro: false,
            pro_since: null,
            pro_until: null,
            has_stripe_subscription: false,
            created_at: "2026-05-15T10:00:00Z",
          }),
          headers: new Headers({ "content-type": "application/json" }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] });
    });
    renderWithQuery(<Sidebar />);
    const link = await screen.findByTestId("upgrade-link");
    expect(link).toBeInTheDocument();
    expect(link).toHaveTextContent("Upgrade to Pro");
  });

  it("hides upgrade link for pro users", async () => {
    mockUseSession.mockReturnValue({
      data: { user: { id: 5, name: "Alice", email: "alice@example.com" } },
    });
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/users/5")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 5,
            email: "alice@example.com",
            name: "Alice",
            interests: "finance",
            preferred_format: "email",
            briefing_depth: 10,
            is_pro: true,
            pro_since: "2026-03-15T00:00:00Z",
            pro_until: null,
            has_stripe_subscription: true,
            created_at: "2026-05-15T10:00:00Z",
          }),
          headers: new Headers({ "content-type": "application/json" }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] });
    });
    renderWithQuery(<Sidebar />);
    // Wait for user data to load
    await screen.findByTestId("user-greeting");
    expect(screen.queryByTestId("upgrade-link")).not.toBeInTheDocument();
  });
});
