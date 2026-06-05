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
});
